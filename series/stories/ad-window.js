(() => {
  const {box,label,circle,path,live,measured,progress,scene}=window.STORY;
  const bg='#101e37', cyan='#64e7df', gold='#ffd368', white='#e3eff7';
  function axes(g,x,y,w,t){
    const dx=w/7;
    for(let i=0;i<=7;i++){
      box(g,x+i*dx,y-39,2,240,'#385068');
      label(g,String(i),x+i*dx-9,y+219,29,white);
    }
    const head=(.14+.86*progress(t,.1,1.55));
    box(g,x,y,w*head,56,cyan,4); box(g,x,y+103,dx*head,56,gold,4);
    circle(g,x+w*head,y+28,12,white);circle(g,x+dx*head,y+131,12,white);
  }
  function draw(g,s,t,H,stage){
    for(let x=30;x<1080;x+=60)for(let y=62;y<1480;y+=60)circle(g,x,y,2.1,'#425675');
    label(g,'点击归因    /    陶瓷杯',59,118,35,cyan);
    if(stage==='hook'){
      label(g,'同一广告词，两种口径',62,249,80,white);
      live(g,s,t,H,60,417,960,cyan,bg,'读取投放口径');
      label(g,'7 天',74,1065,98,cyan);label(g,'与',334,1065,54,white);label(g,'1 天',486,1065,98,gold);
      axes(g,82,1174,882,t); measured(g,s,t,66,990,white);
    }else if(stage==='live'){
      live(g,s,t,H,48,346,984,cyan,bg,'读入两平台报表');
      axes(g,85,1053,871,t);
    }else if(stage==='compare'){
      label(g,'同一个词，两张报表',60,317,84,white);
      label(g,'6',72,606,225,cyan);label(g,'4',610,606,225,gold);
      label(g,'平台甲',83,803,48,white);label(g,'平台乙',620,803,48,white);
      axes(g,82,1042,875,t);
    }else{
      label(g,stage==='claim'?'领取投放助手':stage==='align'?'从点击那天开始':'按窗口读回报',63,302,88,white);
      axes(g,86,548,874,t);
      const sweep=86+874*((t*.32)%1);
      path(g,[[sweep,479],[sweep,727]],white,4);
      if(stage!=='claim'){
        label(g,'7 日点击    ROAS  6',80,1059,66,cyan);
        label(g,'1 日点击    ROAS  4',80,1211,66,gold);
      }
    }
  }
  for(const st of ['hook','compare','live','align','resolution','claim'])scene('ad-window',st,{bg,beats:[.5,1.35,2.85,4.25]},draw);
})();
