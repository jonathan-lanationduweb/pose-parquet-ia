/**
 * Moteur de rendu — WebGL 2, sans bibliothèque.
 *
 * Même chaîne que le moteur Canvas, mêmes données, même résultat attendu.
 * Trois choses le distinguent, et ce sont les trois raisons de l'écrire :
 *
 * 1. **Filtrage anisotrope matériel.** En perspective rasante, un pixel du
 *    fond de pièce couvre une longue bande de texture. Un moteur logiciel doit
 *    choisir : filtrer large (le fond devient une bouillie) ou serré (il
 *    fourmille). Le GPU sait échantillonner le long du grand axe, gratuitement.
 *    C'est exactement le défaut qui faisait ressembler le rendu à une image
 *    plaquée : les lames du fond n'avaient plus de lames.
 *
 * 2. **Le coût ne dépend plus du nombre de zones.** Une scène à quatre plans
 *    coûte quatre quadrilatères, pas quatre parcours d'image.
 *
 * 3. **Le matériau est un uniforme.** Changer de parquet, c'est changer deux
 *    textures : le rendu suit le doigt au lieu de se recalculer.
 *
 * Pas de Three.js : nous projetons des quadrilatères texturés avec un shader
 * maison — pas de graphe de scène, pas de caméra 3D, pas de chargeur, pas de
 * système de lumières. Le raisonnement complet est dans
 * docs/renderer-canvas-vs-webgl.md.
 *
 * Le moteur Canvas reste en place : il sert quand WebGL 2 manque, et il sert
 * de référence — les deux doivent donner la même image.
 */
import { zoneTransform, tileLight } from './geometry.js';
import { TILE_METERS, patternProfile } from './texture.js';

const VERTEX = `#version 300 es
in vec2 aUnit;
uniform mat3 uQuad;      // carré unité → pixels image
uniform vec2 uViewport;
void main() {
  vec3 p = uQuad * vec3(aUnit, 1.0);
  vec2 pix = p.xy / p.z;
  gl_Position = vec4(pix.x / uViewport.x * 2.0 - 1.0, 1.0 - pix.y / uViewport.y * 2.0, 0.0, 1.0);
}`;

const FRAGMENT = `#version 300 es
precision highp float;
out vec4 outColor;

uniform sampler2D uMask;      // R = zone, G = couverture, B = occlusion
uniform sampler2D uAlbedo;    // tuile de bois, mipmaps + anisotrope
uniform sampler2D uReliefMap; // R,G = pente ; B = rugosité locale
uniform sampler2D uShading;   // RGB = gain de lumière par canal, A = contact
uniform sampler2D uGloss;     // résidu clair, pour les finitions brillantes

uniform vec2  uViewport;
uniform mat3  uInverse;     // pixels image → carré unité
uniform vec2  uMeters;      // largeur, profondeur réelles du plan
uniform vec2  uOrigin;      // décalage de la trame, en mètres
uniform vec2  uRot;         // cos, sin de l'orientation du motif
uniform float uTileMeters;  // mètres couverts par une tuile
uniform float uRowsPerTile; // rangées de lames dans une tuile
uniform float uJitter;      // amplitude du décalage par rangée, 0 = aucun
uniform float uLabel;       // numéro de la zone, 1..255
uniform vec2  uLight;       // direction de la lumière, repère de la tuile
uniform float uStrength;    // report de l'éclairement
uniform float uAmbient;     // plancher de lumière indirecte
uniform float uTint;        // part de la couleur de la lumière
uniform float uReliefGain;  // amplitude du relief
uniform float uGlossGain;   // dose de reflet

void main() {
  // gl_FragCoord a son origine en bas ; l'image, en haut.
  vec2 pix = vec2(gl_FragCoord.x, uViewport.y - gl_FragCoord.y);
  vec2 texel = pix / uViewport;
  vec4 mask = texture(uMask, texel);

  // Chaque zone ne peint que les pixels qui lui appartiennent : les
  // quadrilatères de perspective peuvent donc se recouvrir librement sans que
  // les zones se repeignent l'une l'autre.
  if (abs(mask.r * 255.0 - uLabel) > 0.5) discard;
  float cover = mask.g * (1.0 - mask.b);
  if (cover <= 0.004) discard;

  vec3 n = uInverse * vec3(pix, 1.0);
  if (abs(n.z) < 1e-8) discard;
  vec2 floorM = (n.xy / n.z) * uMeters + uOrigin;

  // L'orientation du motif est appliquée dans le plan du sol, jamais dans
  // l'image : les chevrons d'un Point de Hongrie appartiennent au sol et
  // fuient avec lui.
  vec2 rotated = vec2(
    floorM.x * uRot.x - floorM.y * uRot.y,
    floorM.x * uRot.y + floorM.y * uRot.x
  );
  vec2 uv = rotated / uTileMeters;

  // Rupture de périodicité, rangée par rangée.
  //
  // La tuile couvre 4,80 m et une pièce en fait 6 à 8 : la même séquence de
  // lames revient donc, avec ses nœuds et ses cathédrales au même endroit, et
  // l'œil repère aussitôt un motif qui se répète. Un atlas plus grand coûterait
  // des dizaines de mégaoctets pour le seul plaisir de repousser le problème.
  //
  // On décale plutôt la lecture le long de 'u' d'une valeur propre à chaque
  // rangée de lames. Les rangées gardent leur alignement — le décalage se fait
  // dans la longueur, pas en travers — la tuile se raccorde en 'u', donc rien
  // ne se voit au joint. Et comme l'indice de rangée croît sans borne, deux
  // répétitions de la tuile en profondeur reçoivent des décalages différents :
  // la périodicité tombe sur les deux axes à la fois.
  //
  // Inapplicable aux chevrons, dont les lames traversent les rangées : le
  // moteur y met 'uJitter' à zéro.
  vec2 uvLu = uv;
  if (uJitter > 0.0) {
    float rangee = floor(uv.y * uRowsPerTile);
    // Recurrence doree plutot que fract(sin(x)) : la seconde depend de la
    // precision de sin, qui differe entre le float32 du shader et le float64
    // du moteur Canvas — les deux moteurs n arrangeraient pas les lames de la
    // meme facon, et ils doivent rester comparables.
    uvLu.x += fract(rangee * 0.6180339887) * uJitter;
  }

  // Les dérivées viennent de 'uv', jamais de 'uvLu' : le décalage est constant
  // par rangée, mais il saute d'une rangée à l'autre. Laisser le GPU dériver
  // 'uvLu' lui ferait lire un saut à chaque changement de rangée et choisir un
  // mipmap absurde — une ligne floue apparaîtrait à chaque joint de lame.
  vec3 albedo = textureGrad(uAlbedo, uvLu, dFdx(uv), dFdy(uv)).rgb;
  vec3 relief = textureGrad(uReliefMap, uvLu, dFdx(uv), dFdy(uv)).rgb;

  // Taille du pixel au sol, en mètres : sert à estomper le relief au loin,
  // où un chanfrein de 2 mm ne peut plus être qu'un bruit.
  float footprint = max(length(dFdx(rotated)), length(dFdy(rotated)));
  float near = clamp(0.006 / (footprint + 0.003), 0.0, 1.0);

  float aLum = dot(albedo, vec3(0.2126, 0.7152, 0.0722));

  vec4 lit = texture(uShading, texel);
  float lum = max(0.02, dot(lit.rgb, vec3(0.2126, 0.7152, 0.0722)));
  float raw = 1.0 + uStrength * (pow(lum, 0.88) - 1.0);

  // Relèvement des ombres, sur deux conditions.
  //
  // 1. **Seulement sous la moyenne du sol.** Relever toute la plage coûtait un
  //    tiers à la moitié du relief lumineux (mesuré : 21 → 12 sur le séjour),
  //    et un sol sans modelé se lit comme une plaque posée sur la photo.
  // 2. **Seulement autant que le matériau en a besoin.** Un albédo foncé
  //    multiplié par un gain faible atterrit près de zéro, là où la
  //    quantification 8 bits et le noir de l'écran effacent toute matière : on
  //    ne lit plus un sol sombre, on lit un trou. Un albédo clair a de la
  //    marge et n'a donc rien à protéger — lui appliquer la même correction ne
  //    faisait qu'aplatir son éclairement. Le garde-fou est proportionnel au
  //    manque de marge, pas constant.
  float lift = uAmbient * (1.0 - aLum);
  float shade = clamp(raw < 1.0 ? lift + (1.0 - lift) * raw : raw, 0.42, 1.9);
  // La couleur de la lumière, pas seulement son intensité : un bois neutre au
  // milieu d'une pièce dorée se remarque tout de suite.
  vec3 gain = vec3(shade) + uTint * (lit.rgb - vec3(lum)) * uStrength;

  vec2 slope = (relief.rg - 0.5) * 2.0;
  float bump = clamp(1.0 + dot(slope, uLight) * uReliefGain * near, 0.55, 1.6);

  float specular = 0.0;
  if (uGlossGain > 0.0) {
    specular = texture(uGloss, texel).r * uGlossGain * (1.0 - relief.b) * near;
  }

  // Le reflet emprunte sa couleur au bois plutôt qu'au blanc, et s'atténue sur
  // les teintes sombres. Un ajout quasi blanc sur un albédo foncé ne fait pas
  // briller la matière : il la délave, et la tache de soleil part au gris.
  vec3 teinteReflet = mix(albedo, vec3(0.82, 0.80, 0.76), 0.55);
  vec3 color = albedo * gain * (bump * lit.a) + teinteReflet * specular * (0.35 + 0.65 * aLum);

  // Genou doux sur les hautes lumières. Dans une tache de soleil, un simple
  // écrêtage à 1 efface le bois : la zone devient un aplat blanc. Ici les
  // valeurs au-delà de 0,86 sont comprimées au lieu d'être coupées, et le
  // veinage reste lisible en pleine lumière.
  vec3 over = max(color - 0.86, vec3(0.0));
  color = color - over + over / (1.0 + over * 4.0);

  outColor = vec4(clamp(color, 0.0, 1.0), cover);
}`;

const BLIT_VERTEX = `#version 300 es
in vec2 aPos; out vec2 vUv;
void main() { vUv = vec2(aPos.x, 1.0 - aPos.y); gl_Position = vec4(aPos * 2.0 - 1.0, 0.0, 1.0); }`;

const BLIT_FRAGMENT = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; uniform sampler2D uTex;
void main() { o = vec4(texture(uTex, vUv).rgb, 1.0); }`;

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`Shader refusé : ${log}`);
  }
  return shader;
}

function link(gl, vertex, fragment) {
  const vs = compile(gl, gl.VERTEX_SHADER, vertex);
  const fs = compile(gl, gl.FRAGMENT_SHADER, fragment);
  const prog = gl.createProgram();
  gl.attachShader(prog, vs);
  gl.attachShader(prog, fs);
  gl.linkProgram(prog);
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    throw new Error(`Programme refusé : ${gl.getProgramInfoLog(prog)}`);
  }
  return prog;
}

/** Nos matrices sont écrites en lignes, GLSL les attend en colonnes. */
const transpose = (m) => new Float32Array([m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]]);

/** Matrice carré unité → rectangle de pixels : la surface à rastériser. */
const rectMatrix = (box) => [box.x1 - box.x0, 0, box.x0, 0, box.y1 - box.y0, box.y0, 0, 0, 1];

/** float32 → half float, pour la carte d'éclairement. */
function toHalf(values) {
  const out = new Uint16Array(values.length);
  const view = new DataView(new ArrayBuffer(4));
  for (let i = 0; i < values.length; i += 1) {
    view.setFloat32(0, values[i]);
    const bits = view.getUint32(0);
    const sign = (bits >>> 16) & 0x8000;
    const exponent = ((bits >>> 23) & 0xff) - 112;
    const mantissa = bits & 0x7fffff;
    if (exponent <= 0) out[i] = sign;
    else if (exponent >= 31) out[i] = sign | 0x7bff;
    else out[i] = sign | (exponent << 10) | (mantissa >>> 13);
  }
  return out;
}

/** Un seul contexte pour tout l'outil : un onglet n'en accorde qu'une poignée. */
let shared = null;

export function glAvailable() {
  if (shared) return true;
  try {
    return Boolean(document.createElement('canvas').getContext('webgl2'));
  } catch (error) {
    void error;
    return false;
  }
}

export function createGlRenderer() {
  if (shared !== null) return shared || null;

  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl2', {
    alpha: false,
    antialias: false,
    depth: false,
    stencil: false,
    premultipliedAlpha: false,
    preserveDrawingBuffer: true, // le canevas est relu pour l'export et la comparaison
    powerPreference: 'high-performance',
  });
  if (!gl) {
    shared = false;
    return null;
  }

  let prog;
  let blit;
  try {
    prog = link(gl, VERTEX, FRAGMENT);
    blit = link(gl, BLIT_VERTEX, BLIT_FRAGMENT);
  } catch (error) {
    console.warn('[visualiseur] WebGL refusé, retour au moteur Canvas.', error);
    shared = false;
    return null;
  }

  const aniso = gl.getExtension('EXT_texture_filter_anisotropic');
  const anisotropy = aniso ? Math.min(16, gl.getParameter(aniso.MAX_TEXTURE_MAX_ANISOTROPY_EXT)) : 1;

  const uniforms = (program, names) => {
    const map = {};
    names.forEach((name) => {
      map[name] = gl.getUniformLocation(program, name);
    });
    return map;
  };
  const u = uniforms(prog, [
    'uQuad', 'uViewport', 'uInverse', 'uMeters', 'uOrigin', 'uRot', 'uTileMeters',
    'uRowsPerTile', 'uJitter',
    'uLabel', 'uLight', 'uStrength', 'uAmbient', 'uTint', 'uReliefGain', 'uGlossGain',
    'uMask', 'uAlbedo', 'uReliefMap', 'uShading', 'uGloss',
  ]);
  const uBlit = uniforms(blit, ['uTex']);

  const quadBuffer = (program, attribute) => {
    const vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
    const location = gl.getAttribLocation(program, attribute);
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location, 2, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);
    return vao;
  };
  const vao = quadBuffer(prog, 'aUnit');
  const blitVao = quadBuffer(blit, 'aPos');

  const makeTexture = (unit, { filter = gl.NEAREST, wrap = gl.CLAMP_TO_EDGE, mips = false } = {}) => {
    const texture = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, wrap);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, wrap);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, mips ? gl.LINEAR_MIPMAP_LINEAR : filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, mips ? gl.LINEAR : filter);
    if (mips && aniso) gl.texParameterf(gl.TEXTURE_2D, aniso.TEXTURE_MAX_ANISOTROPY_EXT, anisotropy);
    return { texture, unit, mips };
  };

  const tex = {
    photo: makeTexture(0),
    mask: makeTexture(1),
    albedo: makeTexture(2, { wrap: gl.REPEAT, mips: true }),
    relief: makeTexture(3, { wrap: gl.REPEAT, mips: true }),
    shading: makeTexture(4, { filter: gl.LINEAR }),
    gloss: makeTexture(5),
  };

  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  const upload = (slot, internal, format, type, width, height, data) => {
    gl.activeTexture(gl.TEXTURE0 + slot.unit);
    gl.bindTexture(gl.TEXTURE_2D, slot.texture);
    gl.texImage2D(gl.TEXTURE_2D, 0, internal, width, height, 0, format, type, data);
    if (slot.mips) gl.generateMipmap(gl.TEXTURE_2D);
  };

  let size = { width: 0, height: 0 };
  let maskBytes = null;
  let glossBytes = null;
  let currentMaterial = null;
  const noGloss = new Uint8Array([0]);

  shared = {
    backend: 'webgl2',
    canvas,
    anisotropy,

    resize(width, height) {
      if (size.width === width && size.height === height) return;
      canvas.width = width;
      canvas.height = height;
      size = { width, height };
      maskBytes = new Uint8Array(width * height * 4);
      glossBytes = new Uint8Array(width * height);
      currentMaterial = null;
    },

    setPhoto(imageData) {
      this.resize(imageData.width, imageData.height);
      upload(tex.photo, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, imageData.width, imageData.height, imageData.data);
    },

    /** Étiquettes, couverture et occlusion tiennent dans une seule texture. */
    setMasks(masks) {
      const labels = masks.labels;
      const coverage = masks.coverage;
      const occlusion = masks.occlusion;
      for (let i = 0, p = 0; i < labels.length; i += 1, p += 4) {
        maskBytes[p] = labels[i];
        maskBytes[p + 1] = coverage[i];
        maskBytes[p + 2] = occlusion ? occlusion[i] : 0;
        maskBytes[p + 3] = 255;
      }
      upload(tex.mask, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, size.width, size.height, maskBytes);
    },

    setShading(shading) {
      upload(tex.shading, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT, shading.width, shading.height, toHalf(shading.rgba));
    },

    setGloss(gloss) {
      if (!gloss) {
        upload(tex.gloss, gl.R8, gl.RED, gl.UNSIGNED_BYTE, 1, 1, noGloss);
        return;
      }
      for (let i = 0; i < gloss.length; i += 1) glossBytes[i] = Math.min(255, Math.round(gloss[i] * 255));
      upload(tex.gloss, gl.R8, gl.RED, gl.UNSIGNED_BYTE, size.width, size.height, glossBytes);
    },

    /** Cartes du matériau. Les mipmaps sont fabriquées par le GPU. */
    setMaterial(id, maps) {
      if (currentMaterial === id) return;
      const side = maps.albedo[0].size;
      upload(tex.albedo, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, side, side, maps.albedo[0].data);
      upload(tex.relief, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, side, side, maps.relief[0].data);
      currentMaterial = id;
    },

    /**
     * Peint la scène : la photo, puis chaque zone de la plus lointaine à la
     * plus proche. Chaque zone n'écrit que ses propres pixels.
     */
    draw({ scene, masks, surfaces, lightDir }) {
      const { width, height } = size;
      gl.viewport(0, 0, width, height);
      gl.disable(gl.DEPTH_TEST);

      // Fond : la photo, à l'identique.
      gl.disable(gl.BLEND);
      gl.useProgram(blit);
      gl.bindVertexArray(blitVao);
      gl.uniform1i(uBlit.uTex, tex.photo.unit);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.useProgram(prog);
      gl.bindVertexArray(vao);
      gl.uniform2f(u.uViewport, width, height);
      gl.uniform1i(u.uMask, tex.mask.unit);
      gl.uniform1i(u.uAlbedo, tex.albedo.unit);
      gl.uniform1i(u.uReliefMap, tex.relief.unit);
      gl.uniform1i(u.uShading, tex.shading.unit);
      gl.uniform1i(u.uGloss, tex.gloss.unit);
      gl.uniform1f(u.uStrength, scene.light.strength);
      gl.uniform1f(u.uAmbient, scene.light.ambient);
      gl.uniform1f(u.uTint, scene.light.tint);

      scene.floorZones.forEach((zone, index) => {
        const surface = surfaces.get(zone.surfaceId);
        const box = masks.box(zone.id);
        if (!surface || !box) return;
        const transform = zoneTransform(zone, width, height);
        if (!transform) return;

        // On rastérise la **boîte du masque**, pas le quadrilatère du plan.
        // Le plan est un repère : il donne la fuite et l'échelle, et il est
        // fréquent que le sol visible le dépasse — un mur qui rentre, un
        // angle qui déborde du cadre. Se limiter au quadrilatère laissait
        // justement des bandes de sol d'origine sur les côtés.
        const rect = rectMatrix(box);

        const config = surface.config;
        const angle = ((config.angle || 0) + zone.plane.rotationDeg) * (Math.PI / 180);
        const surf = surface.maps.surface;
        const light = tileLight(transform.jac, lightDir, angle);
        this.setMaterial(`${surface.material.id}|${config.pattern}|${config.width || 'auto'}`, surface.maps);

        gl.uniformMatrix3fv(u.uQuad, false, transpose(rect));
        gl.uniformMatrix3fv(u.uInverse, false, transpose(transform.M));
        gl.uniform2f(u.uMeters, zone.plane.meters.width, zone.plane.meters.depth);
        gl.uniform2f(u.uOrigin, zone.plane.origin.u, zone.plane.origin.v);
        gl.uniform2f(u.uRot, Math.cos(angle), Math.sin(angle));
        gl.uniform1f(u.uTileMeters, TILE_METERS * (config.scale || 1));
        // Rupture de périodicité : réservée à la pose droite, dont les rangées
        // de lames sont indépendantes. Un chevron traverse les rangées, un
        // décalage les briserait.
        const profil = patternProfile(surface.material, config.pattern, config.width || null);
        const droit = config.pattern === 'lames';
        gl.uniform1f(u.uRowsPerTile, droit ? Math.max(1, Math.round(TILE_METERS / profil.width)) : 1);
        gl.uniform1f(u.uJitter, droit ? 1 : 0);
        gl.uniform1f(u.uLabel, index + 1);
        gl.uniform2f(u.uLight, light.u, light.v);
        gl.uniform1f(u.uReliefGain, surf.relief * 0.9);
        gl.uniform1f(u.uGlossGain, surf.clearcoat * 1.15);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      });

      gl.bindVertexArray(null);
      gl.disable(gl.BLEND);
      return canvas;
    },
  };

  return shared;
}
