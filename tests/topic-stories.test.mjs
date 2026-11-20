import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import vm from 'node:vm';

const source = file => readFileSync(new URL('../series/'+file,import.meta.url),'utf8');
const catalog = JSON.parse(source('catalog.json'));

function geometry(id, stage) {
  const ops = [];
  const screen = {width:960,height:540};
  const cup = {naturalWidth:1200};
  const canvas = new Proxy({}, {get: (_,method) => (...args) => {
    if(method==='createLinearGradient'||method==='createRadialGradient')return {addColorStop(){}};
    if(['roundRect','rect','arc','lineTo','moveTo','drawImage'].includes(method)) {
      // Capture coarse silhouettes independently of color, titles and rotation timing.
      ops.push([method,...args.filter(Number.isFinite).map(n=>Math.round(n/32))]);
    }
    if(method==='drawImage' && args[0]===screen) proofFrames++;
  }});
  let proofFrames=0;
  const helpers = {$: name=>name.endsWith('cup')?cup:{getContext:()=>canvas},frame:()=>screen};
  const ctx=vm.createContext({window:{VISUALS:{}, KIT:{frame(){}}},URL,document:{currentScript:{src:'file:///test/visual.js'}}});
  vm.runInContext(source('story.js'),ctx);
  if(id==='listing-queue')vm.runInContext(source('hook.js'),ctx);
  vm.runInContext(source('stories/'+id+'.js'),ctx);
  vm.runInContext(source('cinema.js'),ctx);
  const module=catalog.find(item=>item.id===id).module;
  ctx.window.installCinema(id,module,['hook','compare','live','align','resolution','claim'].map(s=>id+'_'+s));
  const sc={prices:['a','b'],values:['1','2','3'],head:['a','b'],hook_status:'result',scale_example:'demo'};
  ctx.window.VISUALS[id+'_'+stage].anim(sc,'s0_',1.1,helpers);
  return {signature:JSON.stringify(ops),proofFrames};
}

test('each opening draws its own geometry and displays an actual recording frame',()=>{
  const layouts=new Set();
  for(const {id} of catalog){
    const shot=geometry(id,'hook');
    assert.equal(shot.proofFrames,1,id);
    assert.ok(!layouts.has(shot.signature),'duplicate opening silhouette: '+id);
    layouts.add(shot.signature);
  }
});

test('the six non-ceramic explanation shots have distinct geometry',()=>{
  const layouts=catalog.filter(r=>!r.template).map(r=>geometry(r.id,'align').signature);
  assert.equal(new Set(layouts).size,layouts.length);
});
