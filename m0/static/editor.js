/* Native-resolution raster edits; Konva handles viewport transforms and prompts. */
window.M0Editor = class {
  constructor(container, info, change) {
    this.info=info;this.change=change;this.tool='box';this.radius=12;this.opacity=.45;this.showMask=true;this.points=[];this.labels=[];this.bbox=null;this.operations=[];this.events=[];this.poly=[];this.undoStack=[];this.redoStack=[];
    this.mask=document.createElement('canvas');this.mask.width=info.width;this.mask.height=info.height;this.ctx=this.mask.getContext('2d',{willReadFrequently:true});this.ctx.fillStyle='black';this.ctx.fillRect(0,0,info.width,info.height);
    this.tint=document.createElement('canvas');this.tint.width=info.width;this.tint.height=info.height;
    this.stage=new Konva.Stage({container,width:container.clientWidth,height:Math.max(380,container.clientHeight)});this.layer=new Konva.Layer();this.stage.add(this.layer);this.group=new Konva.Group();this.layer.add(this.group);
    this.rgb=new Konva.Image({listening:false,width:info.width,height:info.height});this.maskNode=new Konva.Image({image:this.tint,listening:false,width:info.width,height:info.height,opacity:this.opacity});this.prompts=new Konva.Group({listening:false});this.group.add(this.rgb,this.maskNode,this.prompts);
    this.stage.on('wheel',e=>{e.evt.preventDefault();let pos=this.stage.getPointerPosition(),s=this.group.scaleX(),next=Math.min(8,Math.max(.12,s*(e.evt.deltaY>0?.9:1.1)));let p={x:(pos.x-this.group.x())/s,y:(pos.y-this.group.y())/s};this.group.scale({x:next,y:next});this.group.position({x:pos.x-p.x*next,y:pos.y-p.y*next});this.layer.batchDraw();});
    this.stage.on('mousedown touchstart',e=>this.down(e));this.stage.on('mousemove touchmove',e=>this.move(e));this.stage.on('mouseup touchend mouseleave',e=>this.up(e));
    this.observer=new ResizeObserver(()=>{this.stage.size({width:container.clientWidth,height:Math.max(380,container.clientHeight)});this.fit();});this.observer.observe(container);
  }
  async load(source){await this.background(source);this.fit();this.undoStack=[this.snapshot()];}
  async background(source){const img=await this.image(source);this.rgb.image(img);this.layer.draw();}
  image(url){return new Promise((resolve,reject)=>{let i=new Image();i.onload=()=>resolve(i);i.onerror=reject;i.src=url;});}
  fit(){let s=Math.min(this.stage.width()/this.info.width,this.stage.height()/this.info.height)*.96;this.group.scale({x:s,y:s});this.group.position({x:(this.stage.width()-this.info.width*s)/2,y:(this.stage.height()-this.info.height*s)/2});this.layer.batchDraw();}
  position(){let p=this.stage.getPointerPosition(),tr=this.group.getAbsoluteTransform().copy().invert(),v=tr.point(p);return {x:Math.min(this.info.width-1,Math.max(0,v.x)),y:Math.min(this.info.height-1,Math.max(0,v.y))};}
  setTool(tool){this.tool=tool;this.group.draggable(tool==='pan');this.stage.container().style.cursor=tool==='pan'?'grab':'crosshair';}
  down(e){if(e.evt.button===2)return;let p=this.position();this.start=p;this.last=p;this.drawing=true;
    if(['positive','negative'].includes(this.tool)){this.points.push([Math.round(p.x),Math.round(p.y)]);this.labels.push(this.tool==='positive'?1:0);this.redrawPrompts();this.push();this.drawing=false;}
    if(this.tool==='polygon_add'||this.tool==='polygon_erase'){this.poly.push([p.x,p.y]);this.redrawPrompts();this.drawing=false;}
    if(['brush','erase'].includes(this.tool)){this.stroke=[p];this.paint(p,p);}
  }
  move(){if(!this.drawing||this.tool==='pan')return;let p=this.position();if(this.tool==='box'){this.bbox=[Math.min(this.start.x,p.x),Math.min(this.start.y,p.y),Math.max(this.start.x,p.x),Math.max(this.start.y,p.y)].map(Math.round);this.redrawPrompts();}
    if(['brush','erase'].includes(this.tool)){this.paint(this.last,p);this.stroke.push(p);this.last=p;}}
  up(){if(!this.drawing)return;this.drawing=false;if(this.tool==='box'){if(this.bbox&& (this.bbox[2]<=this.bbox[0]||this.bbox[3]<=this.bbox[1]))this.bbox=null;this.push();}
    if(['brush','erase'].includes(this.tool)){this.operations.push({type:this.tool,radius:this.radius,points:this.stroke.map(p=>[p.x,p.y]),at:new Date().toISOString()});this.push();}}
  paint(a,b){let c=this.ctx;c.strokeStyle=c.fillStyle=this.tool==='erase'?'black':'white';c.lineWidth=this.radius*2;c.lineCap='round';c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.stroke();c.beginPath();c.arc(b.x,b.y,this.radius,0,Math.PI*2);c.fill();this.displayMask();}
  polygon(){if(this.poly.length<3)throw Error('多边形需要至少三个顶点');let c=this.ctx;c.fillStyle=this.tool==='polygon_erase'?'black':'white';c.beginPath();this.poly.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.fill();this.operations.push({type:this.tool,points:this.poly.slice(),at:new Date().toISOString()});this.poly=[];this.displayMask();this.redrawPrompts();this.push();}
  displayMask(){let d=this.ctx.getImageData(0,0,this.info.width,this.info.height),t=this.tint.getContext('2d'),out=t.createImageData(d.width,d.height);for(let i=0;i<d.data.length;i+=4){let on=d.data[i]>127;d.data[i]=d.data[i+1]=d.data[i+2]=on?255:0;d.data[i+3]=255;out.data[i]=13;out.data[i+1]=211;out.data[i+2]=167;out.data[i+3]=on?255:0;}this.ctx.putImageData(d,0,0);t.putImageData(out,0,0);this.maskNode.opacity(this.showMask?this.opacity:0);this.layer.batchDraw();}
  redrawPrompts(){this.prompts.destroyChildren();if(this.bbox){let [x,y,x1,y1]=this.bbox;this.prompts.add(new Konva.Rect({x,y,width:x1-x,height:y1-y,stroke:'#f5c85d',strokeWidth:3}));}this.points.forEach((p,i)=>this.prompts.add(new Konva.Circle({x:p[0],y:p[1],radius:7,fill:this.labels[i]?'#28ebaa':'#fc6a76',stroke:'white',strokeWidth:2})));if(this.poly.length)this.prompts.add(new Konva.Line({points:this.poly.flat(),stroke:'#faac55',strokeWidth:3,closed:false}));this.layer.batchDraw();}
  async setMask(source,operation=true){let im=await this.image(source);if(im.width!==this.info.width||im.height!==this.info.height)throw Error('掩膜分辨率与原图不匹配');this.ctx.drawImage(im,0,0);this.displayMask();if(operation){this.operations=[];this.push();}}
  snapshot(){return {mask_png:this.mask.toDataURL('image/png'),prompts:{bbox:this.bbox?this.bbox.slice():null,points:this.points.map(p=>p.slice()),labels:this.labels.slice()},edit_history:JSON.parse(JSON.stringify(this.operations)),action_history:JSON.parse(JSON.stringify(this.events))};}
  push(){this.events.push({action:this.tool,at:new Date().toISOString(),prompts:{bbox:this.bbox,points:this.points.map(p=>p.slice()),labels:this.labels.slice()},operation:this.operations.length?this.operations.at(-1):null});this.undoStack.push(this.snapshot());if(this.undoStack.length>30)this.undoStack.shift();this.redoStack=[];this.change(this.snapshot());}
  async restore(s,restoreAudit=false){if(restoreAudit)this.events=JSON.parse(JSON.stringify(s.action_history||[]));if(s.mask_png)await this.setMask(s.mask_png,false);this.bbox=s.prompts?.bbox||null;this.points=s.prompts?.points||[];this.labels=s.prompts?.labels||[];this.operations=s.edit_history||[];this.redrawPrompts();}
  async undo(){if(this.undoStack.length<2)return;this.events.push({action:'undo',at:new Date().toISOString()});this.redoStack.push(this.undoStack.pop());await this.restore(this.undoStack.at(-1));this.change(this.snapshot());}
  async redo(){if(!this.redoStack.length)return;this.events.push({action:'redo',at:new Date().toISOString()});let s=this.redoStack.pop();this.undoStack.push(s);await this.restore(s);this.change(this.snapshot());}
  clearPrompts(){this.points=[];this.labels=[];this.bbox=null;this.poly=[];this.redrawPrompts();this.push();}
  destroy(){this.observer.disconnect();this.stage.destroy();}
};
