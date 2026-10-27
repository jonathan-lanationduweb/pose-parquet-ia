"""Apply reviewed source-pixel annotations to catalogue masks only.

Annotations are scene data, never renderer offsets. Camera/planes, product scale,
light and unrelated objects are unchanged. No inference or image modification.
"""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from app.services.mask_contours import cell_polygons


def raster(shape, polygon, holes=()):
    h, w = shape
    result = np.zeros(shape, np.uint8)
    def fill(poly, value):
        # Sample pixel centres. cv2.fillPoly includes both integer endpoints,
        # whereas the exported polygons describe CELL edges, not their centres.
        xs = np.array([p['x'] * w for p in poly])
        ys = np.array([p['y'] * h for p in poly])
        xx, yy = np.roll(xs, -1), np.roll(ys, -1)
        for y in range(max(0, int(np.floor(ys.min()))), min(h, int(np.ceil(ys.max())))):
            cy = y + .5
            crossing = (ys > cy) != (yy > cy)
            cuts = np.sort(xs[crossing] + (cy - ys[crossing]) * (xx[crossing] - xs[crossing]) / (yy[crossing] - ys[crossing]))
            for left, right in zip(cuts[::2], cuts[1::2]):
                a, b = max(0, int(np.ceil(left - .5))), min(w, int(np.ceil(right - .5)))
                result[y, a:b] = value
    fill(polygon, 1)
    for hole in holes:
        fill(hole, 0)
    return result.astype(bool)


def apply_review(scene, review):
    out = copy.deepcopy(scene)
    w, h = review['imageSize']
    if (w, h) != (scene['image']['width'], scene['image']['height']):
        raise ValueError('Annotations must match the original image size')
    floors = [raster((h, w), z['mask']['polygon'], z['mask'].get('holes', [])) for z in scene['floorZones']]
    objects = [raster((h, w), o['polygon'], o.get('holes', [])) for o in scene.get('occluders', [])]
    changed_floors, changed_objects = set(), set()
    extra_objects = []
    for edit in review['edits']:
        polygon = [{'x': x / w, 'y': y / h} for x, y in edit['polygon']]
        region = raster((h, w), polygon)
        action = edit['action']
        if action in ('floor', 'restore-floor'):
            target = edit.get('zone', 0)
            if target >= len(floors):
                raise ValueError('Review requires the original zone layout before foreground compilation')
            floors[target] |= region
            changed_floors.add(target)
        if action == 'exclude-floor':
            for i in range(len(floors)):
                floors[i] &= ~region
                changed_floors.add(i)
        if action == 'restore-floor':
            for i in range(len(objects)):
                if np.any(objects[i] & region):
                    objects[i] &= ~region
                    changed_objects.add(i)
        if action == 'protect':
            extra_objects.append({'id': 'review-' + edit['id'], 'label': edit['observation'],
                                  'kind': edit.get('kind', 'furniture'), 'polygon': polygon,
                                  'holes': [], 'feather': 0, 'castsShadow': False})
        if action not in ('floor', 'restore-floor', 'exclude-floor', 'protect'):
            raise ValueError('Unknown annotation action: ' + action)
    out['floorZones'] = []
    for i, zone in enumerate(scene['floorZones']):
        if i not in changed_floors:
            out['floorZones'].append(copy.deepcopy(zone))
            continue
        # Boolean cuts can leave detached one-pixel slivers. They carry no
        # usable floor span and must not become separately validated planes.
        components = [part for part in cell_polygons(floors[i]) if part[2] >= 9]
        for j, (polygon, holes, _) in enumerate(components):
            z = copy.deepcopy(zone)
            z['id'] = zone['id'] if j == 0 else zone['id'] + '-review-' + str(j)
            z['mask'] = {'polygon': [p.model_dump() for p in polygon],
                         'holes': [[p.model_dump() for p in hole] for hole in holes]}
            out['floorZones'].append(z)
    out['occluders'] = []
    for i, obj in enumerate(scene.get('occluders', [])):
        if i not in changed_objects:
            out['occluders'].append(copy.deepcopy(obj))
            continue
        for j, (polygon, holes, _) in enumerate(cell_polygons(objects[i])):
            o = copy.deepcopy(obj)
            o['id'] = obj['id'] if j == 0 else obj['id'] + '-review-' + str(j)
            o['polygon'] = [p.model_dump() for p in polygon]
            o['holes'] = [[p.model_dump() for p in hole] for hole in holes]
            out['occluders'].append(o)
    out['occluders'] += extra_objects
    for key in ('camera', 'planes', 'light', 'surfaces', 'image'):
        assert out.get(key) == scene.get(key), key
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    scene = json.loads(args.scene.read_text(encoding='utf8'))
    reviews = json.loads(args.review.read_text(encoding='utf8'))
    out = apply_review(scene, reviews[scene['id']])
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

if __name__ == '__main__':
    main()
