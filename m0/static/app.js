import {Workbench,rotatedFrame,boxOutside,boxAngles,editBoxAxis} from './workbench.js';
const {createApp,markRaw,nextTick}=Vue;
const clone=x=>JSON.parse(JSON.stringify(x));
let draftTimer,refTimer,editorEpoch=0,loadedState=false;
createApp({
 data(){return {state:{revision:0,objects:{}},sceneDraft:null,baseTransform:null,objectDraft:null,selectedId:'',page:'scene',images:[],pointCount:0,loading:true,workbench:null,createMode:false,showOutside:true,highlight:false,angles:[0,0,0],floorAck:false,directionsAck:false,objectAck:false,sceneDirty:false,objectDirty:false,pendingObjects:{},transformTool:'translate',renderStatus:'正在连接高斯渲染…',reviewer:localStorage.getItem('m0_reviewer')||'',saveStatus:'连接服务器…',notice:'',noticeError:false,busy:'',referenceOpen:false,inspectOnly:false,referenceImage:'',referenceMode:'rgb',recommendations:[],editor:null,editorTool:'box',brushSize:12,opacity:.45,samResult:null,candidate:0,referenceAck:false,exportOpen:false,quality:{issues:[]},versions:[],history:[],freezeAck:false,
 editorTools:[['pan','平移'],['box','提示框'],['positive','正点'],['negative','负点'],['brush','画笔'],['erase','橡皮'],['polygon_add','多边形＋'],['polygon_erase','多边形−']]};},
 computed:{objects(){return Object.values({...this.state.objects,...this.pendingObjects}).filter(o=>!o.deleted);},pendingCount(){return Object.keys(this.pendingObjects).length;},objectAngles(){return this.objectDraft?boxAngles(this.objectDraft.bbox):[0,0,0];},transformHint(){return {translate:'拖动彩色箭头移动设备框',scale:'拖动轴端方块改变尺寸；中心方块等比缩放',rotate:'拖动彩色圆环旋转设备框'}[this.transformTool];},outsideScene(){let b=this.objectDraft?.bbox,s=this.sceneDraft?.bbox;if(!b||!s)return false;return boxOutside(b,s);}},
 watch:{reviewer(value){localStorage.setItem('m0_reviewer',value);}},
 methods:{
 async api(path,method='GET',body){const res=await fetch('/api'+path,{method,headers:method==='GET'?{}:{'Content-Type':'application/json','X-M0-Client':'1'},body:body===undefined?undefined:JSON.stringify(body)});let value=await res.json();if(!res.ok)throw Error(value.detail||'请求失败');return value;},
 message(text,error=false){this.notice=text;this.noticeError=error;},
 rememberReviewer(){localStorage.setItem('m0_reviewer',this.reviewer);},
 payload(data){return {...data,revision:this.state.revision,reviewer:this.reviewer};},
 syncWorkbench(){if(!this.sceneDraft||!this.workbench)return;let objects=this.objects.map(o=>o.object_id===this.selectedId&&this.objectDraft?this.objectDraft:o);this.workbench.setData(this.sceneDraft,objects,this.page==='objects'&&this.objectDraft?.visible!==false?this.objectDraft?.bbox:null,this.page==='objects'?this.selectedId:null,{sceneMode:this.page==='scene',showOutside:this.showOutside,highlight:this.highlight});},
 queueDraft(){if(!loadedState)return;clearTimeout(draftTimer);this.saveStatus='正在保存草稿…';draftTimer=setTimeout(()=>this.flushDraft().catch(e=>this.message(e.message,true)),650);},
 stashObject(){if(this.objectDraft&&this.objectDirty)this.pendingObjects[this.selectedId]=clone(this.objectDraft);},
 setTransformTool(mode){this.transformTool=mode;this.createMode=false;this.workbench?.setTool(mode,true);this.queueDraft();},
 editObjectAxis(kind,axis,event){if(!this.objectDraft||this.objectDraft.visible===false)return;const current=kind==='size'?this.objectDraft.bbox.size[axis]:this.objectAngles[axis],digits=kind==='size'?3:1;try{const value=event.target.value;if(value.trim()!==''&&(Math.abs(Number(value)-current)<1e-9||Number(value)===Number(current.toFixed(digits))))return;this.workbench?.commitBox(editBoxAxis(this.objectDraft.bbox,kind,axis,value));}catch(e){this.message(e.message,true);}event.target.value=(kind==='size'?this.objectDraft.bbox.size[axis]:this.objectAngles[axis]).toFixed(digits);},
 async flushDraft(){clearTimeout(draftTimer);if(!this.sceneDraft)return;await this.api('/draft/workspace','PUT',{base_revision:this.state.revision,page:this.page,selectedId:this.selectedId,sceneDraft:this.sceneDraft,objectDraft:this.objectDraft,baseTransform:this.baseTransform,angles:this.angles,floorAck:this.floorAck,directionsAck:this.directionsAck,sceneDirty:this.sceneDirty,objectDirty:this.objectDirty,pendingObjects:this.pendingObjects,transformTool:this.transformTool});this.saveStatus='草稿已自动保存';},
 onBox(box,finished){if(this.page==='scene'){this.sceneDraft.bbox=clone(box);this.sceneDraft.status='draft';this.floorAck=false;this.sceneDirty=true;}else if(this.objectDraft){this.objectDraft.bbox=clone(box);this.objectDraft.status='draft';this.objectDirty=true;this.objectAck=false;this.stashObject();}this.syncWorkbench();if(finished)this.queueDraft();},
 editedObject(){this.objectDraft.status='draft';this.objectDirty=true;this.objectAck=false;this.stashObject();this.queueDraft();},
 rotateScene(){this.sceneDraft.transform=rotatedFrame(this.baseTransform,this.angles);this.sceneDraft.status='draft';this.sceneDirty=true;this.floorAck=false;this.directionsAck=false;this.syncWorkbench();this.queueDraft();},
 flipScene(which){this.baseTransform=rotatedFrame(this.sceneDraft.transform,which==='up'?[180,0,0]:[0,0,180]);this.angles=[0,0,0];this.rotateScene();},
 resetOrientation(){this.baseTransform=clone(this.state.scene.transform);this.angles=[0,0,0];this.rotateScene();},
 async saveScene(confirm=false){if(this.busy)return;this.busy='保存场景范围与几何索引…';try{let s=await this.api('/scene','POST',this.payload({bbox:this.sceneDraft.bbox,transform:this.sceneDraft.transform,status:confirm?'confirmed':'draft',floor_confirmed:this.floorAck,directions_confirmed:this.directionsAck,review_ack:confirm&&this.floorAck&&this.directionsAck}));this.state=s;this.sceneDraft=clone(s.scene);this.baseTransform=clone(s.scene.transform);this.angles=[0,0,0];this.sceneDirty=false;if(this.selectedId&&s.objects[this.selectedId])this.objectDraft=clone(s.objects[this.selectedId]);this.syncWorkbench();await this.flushDraft();this.message(confirm?'场景范围已确认，可以开始工业对象标注。':'场景草稿已保存。');}finally{this.busy='';}},
 async changePage(page){if(this.busy)return;if(this.pendingCount)await this.saveAll();if(this.sceneDirty)await this.saveScene(false);this.workbench.undoStack=[];this.page=page;this.createMode=false;this.objectAck=false;this.showOutside=page==='scene';this.syncWorkbench();this.queueDraft();history.replaceState(null,'','?page='+page+(this.selectedId?'&object='+this.selectedId:''));},

 async armCreate(){this.stashObject();this.createMode=!this.createMode;if(this.createMode)this.message('点击场景中的设备表面创建框，再使用移动、缩放、旋转手柄调整。');},
 async createAt(point){if(this.busy)return;this.stashObject();const scene=this.sceneDraft.bbox,size=scene.size.map((n,i)=>n*(i===2?.3:.075)),center=point.map((p,i)=>Math.max(scene.center[i]-scene.size[i]/2+size[i]/2,Math.min(scene.center[i]+scene.size[i]/2-size[i]/2,p)));
  this.selectedId='draft_'+crypto.randomUUID();this.objectDraft={object_id:this.selectedId,bbox:{center,size,quaternion:[0,0,0,1]},coordinate_version:this.state.scene.coordinate_version,name_zh:'',name_en:'',description_zh:'',description_en:'',granularity:'equipment',status:'draft',visible:true,source:'interactive_3d_click'};
  this.createMode=false;this.objectAck=false;this.objectDirty=true;this.stashObject();this.workbench.undoStack=[];this.syncWorkbench();this.queueDraft();this.message('已添加设备框。可连续添加多个，最后一键保存全部。');},
 async saveAll(){
  if(this.busy)return;this.stashObject();let edits=Object.values(this.pendingObjects);
  if(!edits.length){this.message('全部设备框已保存。');return;}
  this.busy='正在保存全部设备框…';
  try{let result=await this.api('/objects/batch','POST',this.payload({objects:edits}));this.state=result.state;this.selectedId=result.id_mapping[this.selectedId]||this.selectedId;
   this.pendingObjects={};this.objectDirty=false;this.objectDraft=this.selectedId&&!this.state.objects[this.selectedId]?.deleted?clone(this.state.objects[this.selectedId]):null;if(!this.objectDraft)this.selectedId='';
   this.syncWorkbench();await this.flushDraft();this.saveStatus='全部已保存 · r'+this.state.revision;this.message('已一次保存 '+result.saved+' 项设备修改。');
   history.replaceState(null,'','?page='+this.page+(this.selectedId?'&object='+this.selectedId:''));
  }finally{this.busy='';}
 },
 async saveObject(confirm=false){if(!this.objectDraft)return;this.objectDraft.status=confirm?'confirmed':'draft';this.objectDraft.review_ack=confirm&&this.objectAck;this.objectDirty=true;this.stashObject();await this.saveAll();},
 async selectObject(id){if(this.busy||id===this.selectedId)return;this.stashObject();this.selectedId=id;this.objectDraft=clone(this.pendingObjects[id]||this.state.objects[id]);this.objectAck=false;this.objectDirty=!!this.pendingObjects[id];this.createMode=false;this.workbench.undoStack=[];this.syncWorkbench();this.queueDraft();history.replaceState(null,'','?page=objects&object='+id);},
 async toggleVisible(o){this.stashObject();let value=clone(this.pendingObjects[o.object_id]||o);value.visible=o.visible===false;this.pendingObjects[o.object_id]=value;if(this.selectedId===o.object_id){this.objectDraft=clone(value);this.objectDirty=true;}this.syncWorkbench();this.queueDraft();},
 async setAllVisible(visible){this.stashObject();for(let o of this.objects){if(o.visible!==visible)this.pendingObjects[o.object_id]={...clone(o),visible};}if(this.objectDraft){this.objectDraft.visible=visible;this.objectDirty=true;this.stashObject();}this.syncWorkbench();this.queueDraft();},
 async deleteSelected(){if(!this.selectedId)return;let name=this.objectDraft.name_zh||'未命名对象';if(!window.confirm('删除“'+name+'”？点击一键保存后生效，历史修订仍会保留。'))return;let id=this.selectedId;if(id.startsWith('draft_'))delete this.pendingObjects[id];else this.pendingObjects[id]={...clone(this.objectDraft),deleted:true};this.selectedId='';this.objectDraft=null;this.objectDirty=false;this.syncWorkbench();await this.flushDraft();history.replaceState(null,'','?page=objects');},
 async waitJob(job){while(['queued','running'].includes(job.status)){await new Promise(r=>setTimeout(r,500));job=await this.api('/jobs/'+job.job_id);}if(job.status!=='complete')throw Error(job.error||'任务失败');return job.result;},
 async openReference(inspect){if(this.pendingCount)await this.saveAll();if(!inspect&&!this.selectedId)throw Error('请先创建并保存对象粗框。');this.inspectOnly=inspect;this.referenceOpen=true;this.samResult=null;this.referenceAck=false;this.recommendations=[];await nextTick();
  if(this.selectedId&&!inspect){let r=await this.api('/objects/'+this.selectedId+'/recommend','POST',{});this.recommendations=r.recommendations;}
  let ref=!inspect?this.objectDraft?.reference:null;let first=ref?.image_id||this.recommendations[0]?.image_id||this.images.find(i=>i.image_id==='frame_000050')?.image_id||this.images[0].image_id;
  await this.chooseReference(first,this.recommendations.find(r=>r.image_id===first)?.bbox);
 },
 async chooseReference(id,box){if(this.busy)return;await this.flushRefDraft();const epoch=++editorEpoch;this.referenceImage=id;this.referenceMode='rgb';this.samResult=null;this.referenceAck=false;this.editor?.destroy();this.editor=null;await nextTick();let im=this.images.find(i=>i.image_id===id);if(!im)return;
  let editor=markRaw(new window.M0Editor(document.getElementById('reference-editor'),im,()=>this.queueRefDraft()));this.editor=editor;await editor.load('/api/images/'+id);if(epoch!==editorEpoch){editor.destroy();return;}
  editor.radius=this.brushSize;editor.opacity=this.opacity;
  if(this.inspectOnly){editor.setTool('pan');return;}
  let recommended=box||this.recommendations.find(r=>r.image_id===id)?.bbox;if(recommended){editor.bbox=clone(recommended);editor.redrawPrompts();}
  let draft=await this.api('/draft/reference_'+this.selectedId+'_'+id);if(epoch!==editorEpoch)return;
  if(draft?.content?.snapshot){this.samResult=draft.content.samResult;this.candidate=draft.content.candidate||0;await editor.restore(draft.content.snapshot,true);editor.undoStack=[editor.snapshot()];}
  else if(this.objectDraft?.reference?.image_id===id){let ref=this.objectDraft.reference;this.samResult=await this.api('/files/.inference/'+ref.sam_job_id+'/inference.json');this.candidate=ref.candidate;await editor.setMask('/api/files/'+ref.mask_path,false);editor.bbox=ref.prompts.bbox;editor.points=ref.prompts.points||[];editor.labels=ref.prompts.labels||[];editor.redrawPrompts();editor.undoStack=[editor.snapshot()];}
  this.setTool('box');
 },
 queueRefDraft(){clearTimeout(refTimer);refTimer=setTimeout(()=>this.flushRefDraft().catch(e=>this.message(e.message,true)),800);},
 async flushRefDraft(){clearTimeout(refTimer);if(!this.editor||this.inspectOnly||!this.selectedId||!this.referenceImage)return;await this.api('/draft/reference_'+this.selectedId+'_'+this.editor.info.image_id,'PUT',{snapshot:this.editor.snapshot(),samResult:this.samResult,candidate:this.candidate});},
 async closeReference(){await this.flushRefDraft();editorEpoch++;this.editor?.destroy();this.editor=null;this.referenceOpen=false;},
 setTool(t){this.editorTool=t;this.editor?.setTool(t);},
 updateOpacity(){if(this.editor){this.editor.opacity=this.opacity;this.editor.displayMask();}},
 async showOriginal(){await this.editor?.background('/api/images/'+this.referenceImage);this.referenceMode='rgb';},
 async renderReference(){if(this.busy)return;let id=this.referenceImage;this.busy='服务器正在生成真实 3DGS 渲染…';try{let result=await this.waitJob(await this.api('/render/'+id,'POST',{}));if(this.referenceImage===id){await this.editor.background('/api/files/'+result.path);this.referenceMode='render';}}finally{this.busy='';}},
 async runSam(){if(this.busy)return;this.busy='正在执行单张 SAM 推理…';try{await this.showOriginal();let snapshot=this.editor.snapshot();this.samResult=await this.waitJob(await this.api('/sam','POST',{object_id:this.selectedId,image_id:this.referenceImage,prompts:snapshot.prompts}));await this.chooseCandidate(this.samResult.scores.indexOf(Math.max(...this.samResult.scores)));}finally{this.busy='';}},
 async chooseCandidate(i){this.candidate=i;await this.editor.setMask('/api/files/.inference/'+this.samResult.job_id+'/candidate_'+i+'.png');await this.flushRefDraft();},
 async saveReference(confirm){if(!this.samResult)return;this.busy='保存可选参考…';try{this.state=await this.api('/objects/'+this.selectedId+'/reference','POST',this.payload({...this.editor.snapshot(),image_id:this.referenceImage,sam_job_id:this.samResult.job_id,candidate:this.candidate,status:confirm?'confirmed':'draft',review_ack:confirm&&this.referenceAck}));this.objectDraft=clone(this.state.objects[this.selectedId]);this.objectDirty=false;await this.flushDraft();this.message(confirm?'已确认单张训练参考；未执行多视角融合。':'参考草稿已保存。');}finally{this.busy='';}},
 async removeReference(){this.state=await this.api('/objects/'+this.selectedId+'/reference/remove','POST',this.payload({}));this.objectDraft=clone(this.state.objects[this.selectedId]);await this.flushDraft();},
 async openExport(){if(this.pendingCount)await this.saveAll();if(this.sceneDirty)await this.saveScene(false);[this.quality,this.versions,this.history]=await Promise.all([this.api('/quality'),this.api('/versions'),this.api('/history')]);this.freezeAck=false;this.exportOpen=true;},
 async freeze(){this.busy='校验原始来源并冻结不可覆盖版本…';try{let v=await this.api('/freeze','POST',this.payload({review_ack:this.freezeAck}));this.state=await this.api('/state');this.versions=await this.api('/versions');await this.flushDraft();this.message('版本已冻结，可以下载先验 ZIP。');}finally{this.busy='';}}
 },
 async mounted(){
  try{
   [this.state,this.images]=await Promise.all([this.api('/state'),this.api('/images')]);this.sceneDraft=clone(this.state.scene);this.baseTransform=clone(this.sceneDraft.transform);this.floorAck=this.sceneDraft.floor_confirmed;this.directionsAck=this.sceneDraft.directions_confirmed;
   let query=new URLSearchParams(location.search),draft=await this.api('/draft/workspace');this.page=query.get('page')||'scene';
   if(draft?.content?.base_revision===this.state.revision){let d=draft.content;for(let key of ['sceneDraft','objectDraft','selectedId','baseTransform','angles','floorAck','directionsAck','sceneDirty','objectDirty','pendingObjects','transformTool'])if(d[key]!==undefined)this[key]=d[key];if(!query.get('page'))this.page=d.page||'scene';}
   if(query.get('object')&&(this.pendingObjects[query.get('object')]||this.state.objects[query.get('object')])&&!(this.pendingObjects[query.get('object')]||this.state.objects[query.get('object')]).deleted){this.selectedId=query.get('object');if(!this.objectDraft||this.objectDraft.object_id!==this.selectedId)this.objectDraft=clone(this.pendingObjects[this.selectedId]||this.state.objects[this.selectedId]);}
   if(!['scene','objects'].includes(this.page))this.page='scene';this.showOutside=this.page==='scene';
   await nextTick();this.workbench=markRaw(new Workbench(document.getElementById('workbench'),{box:(b,done)=>this.onBox(b,done),creating:()=>this.createMode,create:p=>this.createAt(p).catch(e=>this.message(e.message,true)),select:id=>this.selectObject(id).catch(e=>this.message(e.message,true)),notice:t=>this.message(t),renderStatus:t=>{this.renderStatus=t;}}));
   let [positions,colors]=await Promise.all(['positions','colors'].map(k=>fetch('/api/scene/cloud/'+k).then(r=>{if(!r.ok)throw Error('点云加载失败');return r.arrayBuffer();})));this.pointCount=positions.byteLength/12;await this.workbench.load(positions,colors);this.stashObject();this.syncWorkbench();this.workbench.setTool(this.transformTool);this.workbench.resize();this.loading=false;loadedState=true;this.saveStatus='已恢复保存状态';window.addEventListener('pagehide',()=>this.flushDraft());
  }catch(e){this.message(e.message,true);this.loading=false;}
 }
}).use({install(app){app.config.errorHandler=(err,instance)=>{instance?.message?.(err.message,true);console.error(err);};}}).mount('#app');
