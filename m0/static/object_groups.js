// Display categories; stable object IDs and downstream prior schemas are unchanged.
export const objectCategories=[
 {id:'material_cart',name:'物料车',aliases:['物料车','中央封闭周转料架']},
 {id:'assembly_fixture',name:'装配夹具台',aliases:['装配夹具台','长条装配夹具台','转弯处装配夹具台']},
 {id:'loaded_fixture',name:'带黑色工件的夹具台',aliases:['带黑色工件的夹具台']},
 {id:'multi_tier_rack',name:'多层料架',aliases:['多层料架','多层滚轮料架','中央滚轮供料架','宽幅滚轮供料架']},
 {id:'blue_bins',name:'蓝色箱组',aliases:['蓝色箱组','蓝灰色周转箱组']},
 {id:'air_cooler',name:'立式移动冷风机',aliases:['立式移动冷风机']},
 {id:'workbench',name:'工作台',aliases:['工作台','绿色背板工作台']},
 {id:'compartment_rack',name:'分隔式料架',aliases:['分隔式料架']}
];
export function categoryOf(object){const name=(object.name_zh||'').trim().replace(/[\s\d]+$/,'');return objectCategories.find(c=>c.aliases.includes(name))?.id||'uncategorized';}
export function groupObjects(objects){
 const groups=[...objectCategories,{id:'uncategorized',name:'未分类'}].map(c=>({...c,objects:[]}));
 for(const o of objects)if(!o.deleted)groups.find(c=>c.id===categoryOf(o)).objects.push(o);
 for(const g of groups)g.objects.sort((a,b)=>{const ai=Number((a.name_zh||'').match(/\d+\s*$/)?.[0]),bi=Number((b.name_zh||'').match(/\d+\s*$/)?.[0]);return ai&&bi?ai-bi:a.bbox.center[1]-b.bbox.center[1]||a.bbox.center[0]-b.bbox.center[0];});
 return groups.filter(g=>g.objects.length);
}
