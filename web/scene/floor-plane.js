import {add,subtract,times,dot,cross,normalized} from './camera-model.js';
/** Metres in a fixed orthonormal basis. The adapter preserves the original
 * reference-square origin, so continuous zones keep their existing pattern phase.
 */
export class FloorPlane {
  constructor({origin,originWorld=origin,axisU,axisV,normal,widthMeters,depthMeters}) {
    if(![...originWorld,...axisU,...axisV,widthMeters,depthMeters].every(Number.isFinite)||widthMeters<=0||depthMeters<=0)throw Error('Invalid metric floor');
    if(Math.abs(Math.hypot(...axisU)-1)>1e-6||Math.abs(Math.hypot(...axisV)-1)>1e-6||Math.abs(dot(axisU,axisV))>1e-6)throw Error('Floor axes must be orthonormal');
    this.origin=[...originWorld];this.axisU=[...axisU];this.axisV=[...axisV];
    this.normal=normal?normalized(normal):normalized(cross(axisU,axisV));
    if(Math.abs(dot(this.normal,axisU))>1e-6||Math.abs(dot(this.normal,axisV))>1e-6)throw Error('Invalid floor normal');
    this.widthMeters=widthMeters;this.depthMeters=depthMeters;
  }
  floorLocalToWorld(u,v) {return add(this.origin,add(times(this.axisU,u),times(this.axisV,v)));}
  worldToFloorLocal(point) {const p=subtract(point,this.origin);return {u:dot(p,this.axisU),v:dot(p,this.axisV)};}
  pixelToFloorLocal(point,camera) {const p=camera.pixelToFloor(point,this);return p?this.worldToFloorLocal(p):null;}
  cameraHeight(camera) {return Math.abs(dot(this.normal,subtract(camera.C,this.origin)));}
  toJSON(){return {origin:[...this.origin],axisU:[...this.axisU],axisV:[...this.axisV],normal:[...this.normal],widthMeters:this.widthMeters,depthMeters:this.depthMeters};}
}
