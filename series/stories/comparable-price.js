(() => {
  const {box,label,path,circle,at,live,measured,progress,scene}=window.STORY;
  const bg='#efeadb', ink='#263b31', leaf='#34654c', coral='#c65a38';
  function ruler(g,y,t){
    box(g,54,y,974,11,ink);
    for(let i=0;i<43;i++)box(g,59+i*23,y+9,3,i%5===0?43:19,ink);
    const x=522+112*Math.sin(t*1.4);
    path(g,[[x-24,y-32],[x+24,y-32],[x,y+2]],coral,0,true);
  }
  function jaw(g,x,y,flip,t){
    at(g,x,y,0,()=>{g.scale(flip,1);path(g,[[0,0],[0,122],[95,174],[95,226],[-35,150],[-35,0]],ink,0,true);});
  }
  function draw(g,s,t,H,stage){
    const grip=progress(t,.05,1.6);
    label(g,'可比快照  /  价格校准',61,121,36,leaf);
    if(stage==='hook'){
      label(g,'这两口价，能比吗？',67,276,89,ink);ruler(g,408,t);
      live(g,s,t,H,108,578,864,leaf,'#fff5d8','对照同款快照');
      jaw(g,53+46*grip,373,1,t);jaw(g,1027-46*grip,373,-1,t);
      label(g,s.values[0],73,1218,95,ink,443);label(g,s.values[1],553,1218,95,coral,449);
      label(g,'本店',87,1327,48,leaf);label(g,'可比竞品',566,1327,48,coral);
      measured(g,s,t,69,1473,ink);
    }else if(stage==='live'){
      label(g,'打开可比判定',62,292,96,ink);
      live(g,s,t,H,44,514,992,leaf,'#fff5d8','核对匹配结果');ruler(g,1240,t);
    }else if(stage==='align'){
      label(g,'逐项校准口径',61,293,95,ink);
      ruler(g,436,t);
      const travel=progress(t,.15,1.45);
      jaw(g,125+195*travel,478,1,t);jaw(g,955-195*travel,478,-1,t);
      label(g,'本店 ↔ 竞品',321,774,66,leaf,510);
      ['规格','价格类型','币种','货号'].forEach((v,i)=>{
        const p=progress(t,.25+i*.60,.48),x=106+(i%2)*485,y=1000+155*Math.floor(i/2);
        at(g,x+49,y,-.11*(1-p),()=>{
          circle(g,0,0,37,p===1?leaf:'#c7c5af');
          if(p>.1)path(g,[[-17,0],[-4,13],[18*p,-15*p]],'#fff8e5',6);
        });
        label(g,v,x+104,y,53,ink,333);
      });
    }else{
      label(g,stage==='claim'?'领取比价助手':stage==='compare'?'把同款摆到一起':'量出本店价差',60,302,94,ink);
      ruler(g,536,t);
      const y=805+22*Math.sin(t*1.3);
      label(g,s.values[0],65,y,92,ink,450);label(g,s.values[1],555,y,92,coral,450);
      if(stage!=='claim'){
        label(g,'本店',75,y+103,49,leaf);label(g,'可比竞品',569,y+103,49,coral);
        if(stage==='resolution')label(g,'低 ¥1.10',94,1209,152,leaf);
      }
    }
  }
  for(const st of ['hook','compare','live','align','resolution','claim'])scene('comparable-price',st,{bg,beats:[.62,1.68,3.14,4.71]},draw);
})();
