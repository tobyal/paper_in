// Frame scheduling contracts; no browser, GPU, production annotations or mocked UI screenshots.
import assert from 'node:assert/strict';
import {Workbench} from '../static/workbench.js';
import * as THREE from '../static/vendor/three/three.module.js';

const tick=()=>new Promise(resolve=>setTimeout(resolve,5));
async function until(check){const end=Date.now()+1500;while(!check()){assert.ok(Date.now()<end,'frame scheduler did not progress');await tick();}}
function fixture(){
 const w=Object.create(Workbench.prototype),camera=new THREE.PerspectiveCamera(48,2,.01,100);
 camera.position.set(1,2,10);camera.updateMatrixWorld(true);
 const rect={left:0,top:0,right:800,bottom:400,width:800,height:400};
 Object.assign(w,{mode:'object',viewKey:'confirmed-scene',coordinateVersion:'coord_fixture',showOutside:false,renderEpoch:0,
  scene:new THREE.Scene(),sceneBox:{center:[0,0,0],size:[5,5,5]},points:{visible:false},boxes:{},axes:{},selected:{},
  root:{dataset:{},getBoundingClientRect:()=>rect},gizmo:{},gizmoHelper:{},
  callbacks:{renderStatus:message=>{w.status=message;}},
  views:[{camera,el:{clientWidth:800,clientHeight:400,getBoundingClientRect:()=>rect},controls:{target:new THREE.Vector3(),update(){w.cameraChanged();}}}],
  requests:[],draws:[],renderer:{setScissorTest(){},setViewport(){},setScissor(){},render(scene,usedCamera){w.draws.push({camera:usedCamera.clone(),texture:scene.background,pointsVisible:w.points.visible});}}
 });
 w.fetchGaussianFrame=payload=>new Promise((resolve,reject)=>w.requests.push({payload,resolve,reject}));
 w.finish=(i)=>{const texture=new THREE.Texture();w.requests[i].resolve({texture,gaussians:123});return texture;};
 return w;
}
const w=fixture();
w.cameraChanged();w.render();assert.equal(w.points.visible,false);assert.equal(w.boxes.visible,false);
await tick();assert.equal(w.requests.length,1);
// Keep moving while the first request is in flight. A completed Gaussian frame must still appear.
for(let i=0;i<25;i++){w.views[0].camera.position.x=10+i;w.cameraChanged();}
assert.equal(w.requests.length,1);
const first=w.finish(0);await until(()=>w.requests.length===2);w.render();
assert.equal(w.nativeTexture,first);assert.equal(w.presentedCamera.position.x,1);
assert.equal(w.draws.at(-1).camera.position.x,1);assert.equal(w.draws.at(-1).pointsVisible,false);
assert.equal(w.requests.length,2);assert.equal(w.requests[1].payload.camera_world[0][3],34);
// Hold the existing Gaussian image/camera pair while the successor catches up.
w.views[0].camera.position.x=50;w.cameraChanged();w.render();
assert.equal(w.scene.background,first);assert.equal(w.draws.at(-1).camera.position.x,1);
const second=w.finish(1);await until(()=>w.requests.length===3);w.render();
assert.equal(w.nativeTexture,second);assert.equal(w.presentedCamera.position.x,34);assert.equal(w.requests.length,3);
// Network errors retain the last Gaussian frame, never a point-cloud fallback.
w.requests[2].reject(Error('simulated connection loss'));await tick();w.render();
assert.equal(w.scene.background,second);assert.equal(w.points.visible,false);assert.match(w.status,/保留上一帧/);
assert.equal(w.requests.length,3);
// A pointer event burst must not restart the request timer indefinitely.
w.cameraChanged();const scheduled=w.roamTimer;
for(let i=0;i<30;i++)w.cameraChanged();assert.equal(w.roamTimer,scheduled);
await tick();assert.equal(w.requests.length,4);
// Manipulation snaps navigation to the displayed pose and excludes an older in-flight frame.
w.manipulating=true;w.adoptPresentedView();assert.equal(w.views[0].camera.position.x,34);
const interrupted=w.finish(3);let disposed=false;interrupted.dispose=()=>{disposed=true;};
await tick();assert.equal(disposed,true);assert.equal(w.nativeTexture,second);assert.equal(w.requests.length,4);
w.manipulating=false;
// Context changes hide outdated overlays and reject obsolete scene content.
w.cameraChanged();await tick();assert.equal(w.requests.length,5);
w.viewKey='new-scene';w.cameraChanged();w.render();assert.equal(w.points.visible,false);assert.equal(w.boxes.visible,false);
w.finish(4);await until(()=>w.requests.length===6);assert.equal(w.presentedContext,'confirmed-scene');assert.equal(w.requests.length,6);
w.finish(5);await tick();w.render();assert.equal(w.presentedContext,'new-scene');assert.equal(w.boxes.visible,true);
// Step 01 deliberately keeps its existing point-cloud geometry views.
w.mode='scene';w.cameraChanged();w.render();assert.equal(w.points.visible,true);
clearTimeout(w.roamTimer);w.nativeTexture.dispose();
console.log(JSON.stringify({status:'passed',checks:['frames progress during input','single in-flight request','latest-pose coalescing','image/camera atomic presentation','no object-mode point drawing','network error retains Gaussian frame','no debounce starvation','gizmo camera synchronization','obsolete context rejection','scene-page compatibility']}));
