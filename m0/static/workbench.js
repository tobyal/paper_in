import * as THREE from './vendor/three/three.module.js';
import {OrbitControls} from './vendor/three/OrbitControls.js';
import {TransformControls} from './vendor/three/TransformControls.js';

const edges=[[0,1],[0,2],[0,4],[1,3],[1,5],[2,3],[2,6],[3,7],[4,5],[4,6],[5,7],[6,7]];
const quaternion=b=>new THREE.Quaternion(...(b.quaternion||[0,0,0,1]));
const corners=b=>[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>new THREE.Vector3(x*b.size[0]/2,y*b.size[1]/2,z*b.size[2]/2).applyQuaternion(quaternion(b)).add(new THREE.Vector3(...b.center)))));
const matrix=a=>new THREE.Matrix4().set(...a.flat());
export function boxOutside(b,s){return corners(b).some(p=>p.toArray().some((x,i)=>Math.abs(x-s.center[i])>s.size[i]/2+1e-7));}
export function rotatedFrame(base,angles){let r=new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(...angles.map(x=>x*Math.PI/180),'ZYX'));r.multiply(matrix(base));let a=r.elements;return Array.from({length:4},(_,i)=>Array.from({length:4},(_,j)=>a[j*4+i]));}
export function boxAngles(box){return new THREE.Euler().setFromQuaternion(quaternion(box).normalize(),'XYZ').toArray().slice(0,3).map(n=>THREE.MathUtils.radToDeg(n));}
export function editBoxAxis(box,kind,axis,value){
 const n=Number(value);if(String(value).trim()===''||!Number.isFinite(n)||(kind==='size'&&n<.005))throw Error(kind==='size'?'尺寸必须是不小于 0.005 的数值。':'请输入有效角度。');
 const b=JSON.parse(JSON.stringify(box));if(kind==='size')b.size[axis]=n;
 else{const angles=boxAngles(box);angles[axis]=n;b.quaternion=new THREE.Quaternion().setFromEuler(new THREE.Euler(...angles.map(THREE.MathUtils.degToRad),'XYZ')).normalize().toArray();}return b;
}
// Clip in camera space before projection; edges crossing the eye must not explode across the screen.
export function boxScreenPath(box,camera,width,height){
 const points=corners(box).map(p=>p.applyMatrix4(camera.matrixWorldInverse)),near=-camera.near*1.001;
 return edges.map(([i,j])=>{let a=points[i].clone(),b=points[j].clone();if(a.z>near&&b.z>near)return '';
  if(a.z>near)a.lerp(b,(near-a.z)/(b.z-a.z));else if(b.z>near)b.lerp(a,(near-b.z)/(a.z-b.z));
  a.applyMatrix4(camera.projectionMatrix);b.applyMatrix4(camera.projectionMatrix);
  return `M${((a.x+1)*width/2).toFixed(2)},${((1-a.y)*height/2).toFixed(2)}L${((b.x+1)*width/2).toFixed(2)},${((1-b.y)*height/2).toFixed(2)}`;
 }).join('');
}
export class Workbench {
 constructor(root,callbacks){
  this.root=root;this.callbacks=callbacks;this.boxes=new THREE.Group();this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#0c1522');this.scene.add(this.boxes);this.selected=null;this.undoStack=[];
  this.renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));this.renderer.domElement.className='webgl';root.prepend(this.renderer.domElement);
  this.views=[...root.querySelectorAll('.viewport')].map((el,i)=>{
   let camera=i===0?new THREE.PerspectiveCamera(48,1,.01,10000):new THREE.OrthographicCamera(-10,10,10,-10,.01,10000);
   camera.up.set(0,0,1);let controls=new OrbitControls(camera,el);controls.enableDamping=false;controls.enableRotate=i===0;controls.screenSpacePanning=true;controls.minDistance=.03;controls.maxDistance=1000;controls.zoomSpeed=1.0;
   if(i>0)controls.mouseButtons.LEFT=THREE.MOUSE.PAN;
   controls.addEventListener('change',()=>{this.invalidate();if(i===0)this.cameraChanged();});
   let view={el,camera,controls,svg:el.querySelector('svg'),axes:i===1?[0,1]:i===2?[0,2]:[1,2]};
   if(i>0)this.installHandles(view);
   let down=null;
   el.addEventListener('pointerdown',e=>{if(e.button===0)down=[e.clientX,e.clientY];});
   el.addEventListener('pointerup',e=>{if(i===0&&!this.gizmo?.axis&&!this.manipulating&&performance.now()>(this.suppressPickUntil||0)&&down&&Math.hypot(e.clientX-down[0],e.clientY-down[1])<4&&!e.target.closest('button'))this.pick(e,view);down=null;});
   el.querySelector('.reset-view').addEventListener('click',e=>{e.stopPropagation();this.fitView(view,i,this.focusBox||this.sceneBox);});
   return view;
  });

  this.proxy=new THREE.Object3D();this.scene.add(this.proxy);
  this.gizmo=new TransformControls(this.views[0].camera,this.views[0].el);this.gizmo.setSize(1.15);this.gizmo.setSpace('local');this.gizmoHelper=this.gizmo.getHelper();this.scene.add(this.gizmoHelper);
  this.gizmo.addEventListener('change',()=>this.invalidate());
  this.gizmo.addEventListener('dragging-changed',e=>{this.manipulating=e.value;this.views[0].controls.enabled=!e.value;if(e.value)this.adoptPresentedView();else this.suppressPickUntil=performance.now()+150;});
  this.gizmo.addEventListener('mouseDown',()=>{if(this.selected){this.undoStack.push(JSON.parse(JSON.stringify(this.selected)));if(this.undoStack.length>30)this.undoStack.shift();}});
  this.gizmo.addEventListener('objectChange',()=>{if(!this.manipulating)return;this.proxy.scale.set(Math.max(.005,Math.abs(this.proxy.scale.x)),Math.max(.005,Math.abs(this.proxy.scale.y)),Math.max(.005,Math.abs(this.proxy.scale.z)));this.callbacks.box({center:this.proxy.position.toArray(),size:this.proxy.scale.toArray(),quaternion:this.proxy.quaternion.clone().normalize().toArray()},false);});
  this.gizmo.addEventListener('mouseUp',()=>{if(this.selected)this.callbacks.box(this.selected,true);});
  this.views[0].el.tabIndex=0;this.views[0].el.addEventListener('pointerdown',()=>this.views[0].el.focus({preventScroll:true}));
  this.views[0].el.addEventListener('keydown',e=>{if(this.mode!=='object'||e.target.closest('input,textarea'))return;let k=e.key.toLowerCase(),v=this.views[0];if(!['w','a','s','d','q','e'].includes(k))return;e.preventDefault();let direction=new THREE.Vector3(k==='a'?-1:k==='d'?1:0,k==='q'?-1:k==='e'?1:0,k==='w'?-1:k==='s'?1:0).applyQuaternion(v.camera.quaternion).multiplyScalar(Math.max(...this.sceneBox.size)*.018*(e.shiftKey?3:1));v.camera.position.add(direction);v.controls.target.add(direction);v.controls.update();this.cameraChanged();this.invalidate();});
  this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(root);this.dirty=true;
  this.animate=()=>{this.animation=requestAnimationFrame(this.animate);if(this.dirty){this.dirty=false;this.render();}};this.animate();
 }
 async load(positions,colors){
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(new Float32Array(positions),3));
  geometry.setAttribute('color',new THREE.BufferAttribute(new Uint8Array(colors),3,true));geometry.computeBoundingSphere();
  this.material=new THREE.ShaderMaterial({uniforms:{pointSize:{value:2.1*this.renderer.getPixelRatio()},boundsMin:{value:new THREE.Vector3(-1e5,-1e5,-1e5)},boundsMax:{value:new THREE.Vector3(1e5,1e5,1e5)},objectMin:{value:new THREE.Vector3()},objectMax:{value:new THREE.Vector3()},objectCenter:{value:new THREE.Vector3()},objectRotation:{value:new THREE.Matrix3()},objectHalf:{value:new THREE.Vector3()},showOutside:{value:1},highlight:{value:0}},
   vertexShader:'attribute vec3 color; varying vec3 vColor; varying vec3 pWorld; uniform float pointSize; void main(){vColor=color;pWorld=(modelMatrix*vec4(position,1.)).xyz;gl_Position=projectionMatrix*viewMatrix*vec4(pWorld,1.);gl_PointSize=pointSize;}',
   fragmentShader:'varying vec3 vColor; varying vec3 pWorld; uniform vec3 boundsMin,boundsMax,objectMin,objectMax,objectCenter,objectHalf; uniform mat3 objectRotation; uniform float showOutside,highlight; void main(){if(length(gl_PointCoord-vec2(.5))>.5)discard;bool outside=any(lessThan(pWorld,boundsMin))||any(greaterThan(pWorld,boundsMax));if(outside&&showOutside<.5)discard;vec3 c=vColor;if(outside)c=mix(vec3(.047,.08,.13),c,.13);else if(highlight>.5&&all(lessThanEqual(abs(objectRotation*(pWorld-objectCenter)),objectHalf)))c=mix(c,vec3(1.,.77,.3),.23);gl_FragColor=vec4(c,1.);}'});
  this.points=new THREE.Points(geometry,this.material);this.points.matrixAutoUpdate=false;this.scene.add(this.points);this.invalidate();
 }
 setData(scene,objects,selectedBox,selectedId,options={}){
  this.sceneBox=scene.bbox;this.transform=matrix(scene.transform);if(this.points){this.points.matrix.copy(this.transform);this.points.updateMatrixWorld(true);}
  this.selected=selectedBox;this.selectedId=selectedId;this.objects=objects;this.activeBox=options.sceneMode?scene.bbox:selectedBox;let mode=options.sceneMode?'scene':'object',modeChanged=mode!==this.mode,viewChanged=JSON.stringify([scene.transform,scene.bbox,scene.coordinate_version,options.showOutside])!==this.viewKey;this.mode=mode;
  this.coordinateVersion=scene.coordinate_version;this.showOutside=options.showOutside;this.viewKey=JSON.stringify([scene.transform,scene.bbox,scene.coordinate_version,options.showOutside]);
  this.root.classList.toggle('single-view',this.mode==='object');
  if(this.mode==='object'&&selectedBox){if(!this.manipulating){this.proxy.position.fromArray(selectedBox.center);this.proxy.scale.fromArray(selectedBox.size);this.proxy.quaternion.copy(quaternion(selectedBox));}this.gizmo.attach(this.proxy);}else this.gizmo.detach();
  if(modeChanged){this.gizmo.enabled=this.mode==='object';requestAnimationFrame(()=>{this.resize();if(this.mode==='scene')this.views.forEach((v,i)=>{if(i)this.fitView(v,i,this.sceneBox);});this.cameraChanged();});}
  if(viewChanged)this.cameraChanged();
  while(this.boxes.children.length){let a=this.boxes.children[0];this.boxes.remove(a);a.geometry?.dispose();a.material?.dispose();}
  const add=(box,color,opacity)=>{let cs=corners(box),vs=edges.flatMap(([a,b])=>[...cs[a].toArray(),...cs[b].toArray()]);let g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vs,3));this.boxes.add(new THREE.LineSegments(g,new THREE.LineBasicMaterial({color,transparent:true,opacity,depthTest:false})));};
  add(scene.bbox,0x39c3af,.8);objects.filter(o=>o.visible!==false&&o.object_id!==selectedId).forEach(o=>add(o.bbox,0x7697b8,.65));if(selectedBox)add(selectedBox,0xffca67,1);
  const sb=scene.bbox,min=sb.center.map((c,i)=>c-sb.size[i]/2),max=sb.center.map((c,i)=>c+sb.size[i]/2);
  if(this.material){let u=this.material.uniforms;u.boundsMin.value.fromArray(min);u.boundsMax.value.fromArray(max);u.showOutside.value=options.showOutside?1:0;u.highlight.value=selectedBox&&options.highlight?1:0;if(selectedBox){u.objectCenter.value.fromArray(selectedBox.center);u.objectHalf.value.fromArray(selectedBox.size).multiplyScalar(.5);u.objectRotation.value.setFromMatrix4(new THREE.Matrix4().makeRotationFromQuaternion(quaternion(selectedBox))).transpose();u.objectMin.value.fromArray(selectedBox.center.map((c,i)=>c-selectedBox.size[i]/2));u.objectMax.value.fromArray(selectedBox.center.map((c,i)=>c+selectedBox.size[i]/2));}}
  if(this.axes){this.scene.remove(this.axes);this.axes.geometry.dispose();this.axes.material.dispose();}this.axes=new THREE.AxesHelper(Math.max(...sb.size)*.15);this.axes.position.set(sb.center[0]-sb.size[0]/2,sb.center[1]-sb.size[1]/2,sb.center[2]-sb.size[2]/2);this.scene.add(this.axes);
  if(!this.initialized){this.initialized=true;this.reset();}this.invalidate();
 }
 resize(){let w=this.root.clientWidth,h=this.root.clientHeight;this.renderer.setSize(w,h,false);this.views.forEach(v=>{if(!v.el.clientWidth||!v.el.clientHeight)return;let a=v.el.clientWidth/v.el.clientHeight;if(v.camera.isPerspectiveCamera)v.camera.aspect=a;else{let half=(v.camera.top-v.camera.bottom)/2;v.camera.left=-half*a;v.camera.right=half*a;}v.camera.updateProjectionMatrix();});this.cameraChanged();this.invalidate();}
 fitView(v,i,b){
  if(!b||!v.el.clientWidth||!v.el.clientHeight)return;let center=new THREE.Vector3(...b.center),size=Math.max(...b.size),aspect=v.el.clientWidth/v.el.clientHeight;
  v.controls.target.copy(center);v.camera.zoom=1;
  if(i===0){v.camera.position.copy(center).add(new THREE.Vector3(.9,-1.25,1.0).multiplyScalar(size*.85));v.camera.up.set(0,0,1);v.camera.aspect=aspect;}
  else{
   let [a,c]=v.axes,half=Math.max(b.size[c]/2,b.size[a]/(2*aspect))*1.32;v.camera.top=half;v.camera.bottom=-half;v.camera.left=-half*aspect;v.camera.right=half*aspect;
   let dir=i===1?new THREE.Vector3(0,0,1):i===2?new THREE.Vector3(0,-1,0):new THREE.Vector3(1,0,0);
   v.camera.up.set(0,i===1?1:0,i===1?0:1);v.camera.position.copy(center).add(dir.multiplyScalar(size*3+10));
  }
  v.camera.lookAt(center);v.camera.updateProjectionMatrix();v.controls.update();this.invalidate();
 }
 reset(){this.focusBox=null;this.views.forEach((v,i)=>this.fitView(v,i,this.sceneBox));}
 focus(){if(this.selected){this.focusBox={center:this.selected.center.slice(),size:this.selected.size.map(n=>n*2.2)};this.views.forEach((v,i)=>this.fitView(v,i,this.focusBox));}}
 invalidate(){this.dirty=true;}
 render(){
  if(!this.sceneBox)return;let root=this.root.getBoundingClientRect();this.renderer.setScissorTest(true);
  const objectMode=this.mode==='object',ready=this.presentedContext===this.viewKey&&!!this.presentedCamera;
  // The picking geometry is never drawn in the object editor, including while moving or on errors.
  if(this.points)this.points.visible=!objectMode;
  this.boxes.visible=!objectMode||ready;if(this.axes)this.axes.visible=!objectMode||ready;
  this.gizmo.enabled=objectMode&&ready;this.gizmoHelper.visible=objectMode&&ready&&!!this.selected;
  this.gizmo.camera=objectMode&&ready?this.presentedCamera:this.views[0].camera;
  this.views.forEach((v,i)=>{let r=v.el.getBoundingClientRect();if(!r.width||!r.height)return;let x=r.left-root.left,y=root.bottom-r.bottom,camera=objectMode&&i===0&&ready?this.presentedCamera:v.camera;this.renderer.setViewport(x,y,r.width,r.height);this.renderer.setScissor(x,y,r.width,r.height);
   const outlinesVisible=this.boxes.visible;if(i===0&&v.svg)this.boxes.visible=false;this.renderer.render(this.scene,camera);this.boxes.visible=outlinesVisible;
   if(i)this.drawHandles(v);else if(v.svg)this.drawBoxOutlines(v,camera,!objectMode||ready);
  });
 }
 drawBoxOutlines(v,camera,visible){
  v.svg.style.display=visible?'block':'none';if(!visible)return;
  const ns='http://www.w3.org/2000/svg',entries=[{box:this.sceneBox,color:'#40c9b3',width:1.8,kind:'scene'},
   ...(this.objects||[]).filter(o=>o.visible!==false&&o.object_id!==this.selectedId).map(o=>({box:o.bbox,color:'#91caff',width:2.5,kind:'object'})),
   ...(this.selected?[{box:this.selected,color:'#ffd16b',width:3.5,kind:'selected'}]:[])];
  const fragment=document.createDocumentFragment();camera.updateMatrixWorld(true);
  for(const entry of entries){const d=boxScreenPath(entry.box,camera,v.el.clientWidth,v.el.clientHeight);for(const halo of [true,false]){const path=document.createElementNS(ns,'path');path.setAttribute('d',d);path.setAttribute('fill','none');path.setAttribute('stroke',halo?'#07101c':entry.color);path.setAttribute('stroke-width',entry.width+(halo?2.5:0));path.setAttribute('stroke-linejoin','round');path.setAttribute('stroke-linecap','round');path.setAttribute('vector-effect','non-scaling-stroke');path.setAttribute('opacity',halo?'.85':'1');path.dataset.boxOutline=entry.kind;fragment.append(path);}}
  v.svg.replaceChildren(fragment);
 }
 screen(v,p){let r=v.el.getBoundingClientRect(),q=new THREE.Vector3(...p).project(v.camera);return [(q.x+1)*r.width/2,(1-q.y)*r.height/2];}
 unproject(v,x,y){let r=v.el.getBoundingClientRect();return new THREE.Vector3((x-r.left)/r.width*2-1,1-(y-r.top)/r.height*2,0).unproject(v.camera).toArray();}
 installHandles(v){
  const ns='http://www.w3.org/2000/svg';v.handles=[];
  const make=(name,kind)=>{let el=document.createElementNS(ns,kind);el.dataset.handle=name;el.classList.add('box-handle');v.svg.append(el);v.handles.push(el);
   el.addEventListener('pointerdown',e=>{if(e.button!==0||!this.activeBox)return;e.stopPropagation();e.preventDefault();v.controls.enabled=false;el.setPointerCapture(e.pointerId);
    let start=this.unproject(v,e.clientX,e.clientY),original=JSON.parse(JSON.stringify(this.activeBox));this.undoStack.push(original);if(this.undoStack.length>30)this.undoStack.shift();
    const move=ev=>{let now=this.unproject(v,ev.clientX,ev.clientY),b=JSON.parse(JSON.stringify(original));v.axes.forEach((axis,j)=>{let delta=now[axis]-start[axis],direction=name==='center'?0:Number(name.split(',')[j]);if(name==='center')b.center[axis]+=delta;else if(direction){let fixed=original.center[axis]-direction*original.size[axis]/2;let moving=original.center[axis]+direction*original.size[axis]/2+delta;let extent=Math.max(Math.abs(original.size[axis])*.01,.005,direction*(moving-fixed));b.size[axis]=extent;b.center[axis]=fixed+direction*extent/2;}});
     this.callbacks.box(b,false);
    };
    const end=()=>{el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',end);el.removeEventListener('pointercancel',end);v.controls.enabled=true;this.callbacks.box(this.activeBox,true);};
    el.addEventListener('pointermove',move);el.addEventListener('pointerup',end);el.addEventListener('pointercancel',end);
   });return el;};
  v.outline=document.createElementNS(ns,'rect');v.outline.setAttribute('class','box-outline');v.svg.append(v.outline);
  [-1,0,1].forEach(a=>[-1,0,1].forEach(b=>{if(a||b)make(a+','+b,'rect');}));make('center','circle');
 }
 drawHandles(v){
  const b=this.activeBox;v.svg.style.display=b?'block':'none';if(!b)return;
  let c=this.screen(v,b.center),cs=corners(b).map(p=>this.screen(v,p.toArray())),xs=cs.map(p=>p[0]),ys=cs.map(p=>p[1]),lo=[Math.min(...xs),Math.min(...ys)],hi=[Math.max(...xs),Math.max(...ys)];
  v.outline.setAttribute('x',lo[0]);v.outline.setAttribute('y',lo[1]);v.outline.setAttribute('width',hi[0]-lo[0]);v.outline.setAttribute('height',hi[1]-lo[1]);
  v.handles.forEach(el=>{let name=el.dataset.handle;if(name==='center'){el.setAttribute('cx',c[0]);el.setAttribute('cy',c[1]);el.setAttribute('r',7);}else{let [a,d]=name.split(',').map(Number);let p=b.center.slice();p[v.axes[0]]+=a*b.size[v.axes[0]]/2;p[v.axes[1]]+=d*b.size[v.axes[1]]/2;let [x,y]=this.screen(v,p);el.setAttribute('x',x-5);el.setAttribute('y',y-5);el.setAttribute('width',10);el.setAttribute('height',10);}});
 }
 setTool(mode,ensureVisible=false){this.gizmo.setMode(mode);if(ensureVisible&&this.selected){const camera=this.presentedCamera||this.views[0].camera,p=new THREE.Vector3(...this.selected.center).project(camera);if(Math.abs(p.x)>.72||Math.abs(p.y)>.72||p.z< -1||p.z>1)this.focus();}this.invalidate();}
 commitBox(box){if(this.selected){this.undoStack.push(JSON.parse(JSON.stringify(this.selected)));if(this.undoStack.length>30)this.undoStack.shift();this.callbacks.box(box,true);}}
 undo(){let b=this.undoStack.pop();if(b)this.callbacks.box(b,true);}
 pick(e,v){
  if(!this.points||this.mode==='object'&&this.presentedContext!==this.viewKey)return;
  const camera=this.mode==='object'?this.presentedCamera:v.camera;if(!camera)return;
  const r=v.el.getBoundingClientRect(),mouse=new THREE.Vector2((e.clientX-r.left)/r.width*2-1,1-(e.clientY-r.top)/r.height*2),ray=new THREE.Raycaster();ray.setFromCamera(mouse,camera);
  ray.params.Points.threshold=camera.position.distanceTo(this.mode==='object'?this.presentedTarget:v.controls.target)*2*Math.tan(camera.fov*Math.PI/360)/r.height*5;
  if(!this.callbacks.creating()){
   let hits=this.objects.filter(o=>o.visible!==false).map(o=>{let pose=new THREE.Matrix4().compose(new THREE.Vector3(...o.bbox.center),quaternion(o.bbox),new THREE.Vector3(1,1,1)),local=ray.ray.clone().applyMatrix4(pose.clone().invert()),half=new THREE.Vector3(...o.bbox.size).multiplyScalar(.5),p=local.intersectBox(new THREE.Box3(half.clone().negate(),half),new THREE.Vector3());return p?{o,d:p.applyMatrix4(pose).distanceTo(ray.ray.origin)}:null;}).filter(Boolean).sort((a,b)=>a.d-b.d);
   if(hits.length){this.callbacks.select(hits[0].o.object_id);return;}
  }else{
   const hits=ray.intersectObject(this.points,false);
   for(const h of hits){let p=new THREE.Vector3().fromBufferAttribute(this.points.geometry.attributes.position,h.index).applyMatrix4(this.transform),c=this.sceneBox.center,s=this.sceneBox.size;
    if(p.toArray().every((n,i)=>Math.abs(n-c[i])<=s[i]/2)){this.callbacks.create(p.toArray());return;}}
   this.callbacks.notice('此处没有范围内的可见几何，请放大后点击设备表面。');
  }
 }

 cameraChanged(){
  this.renderEpoch=(this.renderEpoch||0)+1;
  if(this.mode!=='object'){
   clearTimeout(this.roamTimer);this.roamTimer=null;this.roamPending=false;
   this.scene.background=new THREE.Color('#0c1522');if(this.points)this.points.visible=true;
   this.callbacks.renderStatus?.('彩色高斯中心预览');return;
  }
  if(this.points)this.points.visible=false;
  const ready=this.presentedContext===this.viewKey&&!!this.nativeTexture;
  this.scene.background=ready?this.nativeTexture:new THREE.Color('#0c1522');
  this.callbacks.renderStatus?.(ready?'真实 3DGS · 更新视角中…':'正在加载真实 3DGS…');
  this.scheduleGaussian();
 }
 scheduleGaussian(){
  if(this.disposed||this.mode!=='object'||this.manipulating)return;
  if(this.roamBusy){this.roamPending=true;return;}
  // Do not restart this timer on each pointermove: navigation must not starve the stream.
  if(this.roamTimer!=null)return;
  this.roamTimer=setTimeout(()=>{this.roamTimer=null;this.renderGaussian();},0);
 }
 adoptPresentedView(){
  // Start box editing from the camera actually shown, not a newer, unrendered navigation pose.
  if(!this.presentedCamera||this.presentedContext!==this.viewKey)return;
  this.roamGeneration=(this.roamGeneration||0)+1;this.roamPending=false;
  clearTimeout(this.roamTimer);this.roamTimer=null;
  const v=this.views[0];v.camera.copy(this.presentedCamera);v.controls.target.copy(this.presentedTarget);v.controls.update();
 }
 async fetchGaussianFrame(payload){
  const response=await fetch('/api/roam/render',{method:'POST',headers:{'Content-Type':'application/json','X-M0-Client':'1'},body:JSON.stringify(payload)});
  if(!response.ok)throw Error((await response.json()).detail||'高斯渲染失败');
  const blob=await response.blob(),url=URL.createObjectURL(blob);let texture;
  try{texture=await new THREE.TextureLoader().loadAsync(url);}finally{URL.revokeObjectURL(url);}
  texture.colorSpace=THREE.SRGBColorSpace;
  return {texture,gaussians:Number(response.headers.get('X-M0-Gaussians'))};
 }
 async renderGaussian(){
  if(this.disposed||this.manipulating||this.mode!=='object'||!this.coordinateVersion)return;
  if(this.roamBusy){this.roamPending=true;return;}this.roamBusy=true;this.roamPending=false;
  const epoch=this.renderEpoch,context=this.viewKey,generation=this.roamGeneration||0,v=this.views[0];v.camera.updateMatrixWorld(true);
  const frameCamera=v.camera.clone(),frameTarget=v.controls.target.clone();
  const cw=v.el.clientWidth,ch=v.el.clientHeight,scale=Math.min(1,1280/Math.max(cw,ch));if(!cw||!ch){this.roamBusy=false;return;}
  const a=frameCamera.matrixWorld.elements,camera_world=Array.from({length:4},(_,i)=>Array.from({length:4},(_,j)=>a[j*4+i]));
  try{
   const {texture,gaussians}=await this.fetchGaussianFrame({camera_world,width:Math.max(64,Math.round(cw*scale)),height:Math.max(64,Math.round(ch*scale)),fov:frameCamera.fov,coordinate_version:this.coordinateVersion,show_outside:this.showOutside});
   if(this.disposed||this.mode!=='object'||context!==this.viewKey||generation!==(this.roamGeneration||0)||this.manipulating){texture.dispose();return;}
   // Present every completed frame, with its exact camera, even while new input is arriving.
   // Only one request is in flight; its successor samples the newest desired pose.
   this.nativeTexture?.dispose();this.nativeTexture=texture;this.scene.background=texture;
   this.presentedCamera=frameCamera;this.presentedTarget=frameTarget;this.presentedContext=context;
   if(this.points)this.points.visible=false;
   this.root.dataset.gaussianFrame=String((this.presentedFrames||0)+1);this.presentedFrames=(this.presentedFrames||0)+1;
   this.callbacks.renderStatus?.('真实 3DGS · '+gaussians.toLocaleString()+' 高斯');this.invalidate();
  }catch(e){if(this.mode==='object')this.callbacks.renderStatus?.((this.nativeTexture?'真实 3DGS · 保留上一帧：':'高斯画面暂不可用：')+e.message);}
  finally{this.roamBusy=false;if(this.roamPending||epoch!==this.renderEpoch){this.roamPending=false;this.scheduleGaussian();}}
 }
 dispose(){this.disposed=true;clearTimeout(this.roamTimer);this.gizmo.dispose();this.nativeTexture?.dispose();cancelAnimationFrame(this.animation);this.observer.disconnect();this.views.forEach(v=>v.controls.dispose());this.renderer.dispose();}
}
