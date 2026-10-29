var REAL = $.getenv("CNF_ROOT");
if(!REAL || REAL.length < 2) REAL = "/Users/shu/Library/CloudStorage/GoogleDrive-antonsukeloic@gmail.com/My Drive/5HU/CryptoNewsFactory";
REAL = REAL.replace(/\\/g, "/");
var logf = new File(REAL + "/engine/render_log.txt");
function log(m){ logf.open("a"); logf.writeln(m); logf.close(); }
try {
  logf.open("w"); logf.writeln("start root="+REAL); logf.close();
  var jf = new File(REAL + "/engine/current_job.json"); jf.open("r"); var raw = jf.read(); jf.close();
  var job = eval("(" + raw + ")");
  log("job scenes=" + job.scenes.length);
  var proj = app.project, comp = null;
  for (var i=1;i<=proj.numItems;i++){var it=proj.item(i); if(it instanceof CompItem && it.name===job.comp){comp=it;break;}}
  if(!comp){ log("ERROR no comp "+job.comp+" items="+proj.numItems); }
  else {
    comp.width = 1080; comp.height = 1920;
    log("comp 9:16 "+comp.width+"x"+comp.height);
    function imp(rel){var f=new File(REAL+"/"+rel.replace(/\\/g,"/")); if(!f.exists){log("MISSING "+f.fsName); throw new Error("missing "+rel);} return proj.importFile(new ImportOptions(f));}
    while(comp.numLayers>0) comp.layer(1).remove();
    var voiceDur = 0;
    if(job.voice){ var vf = imp(job.voice); var vl = comp.layers.add(vf); vl.startTime=0; voiceDur = vf.duration; log("voiceDur="+voiceDur); }
    var scriptTotal=0; for(var s=0;s<job.scenes.length;s++) scriptTotal += Number(job.scenes[s].duration);
    var target = (voiceDur>0.1) ? voiceDur : scriptTotal;
    comp.duration = target; log("target dur="+target);
    var scale = (scriptTotal>0) ? (target/scriptTotal) : 1;
    var Z = 1.12;
    var t=0;
    for(var k=0;k<job.scenes.length;k++){
      var sc=job.scenes[k]; var fo=imp(sc.image); var L=comp.layers.add(fo);
      var endT = (k===job.scenes.length-1) ? target : (t + Number(sc.duration)*scale);
      L.startTime=t; L.inPoint=t; L.outPoint=endT;
      var base = Math.max(comp.width/fo.width, comp.height/fo.height)*100;
      var sp = L.property("Transform").property("Scale");
      var sFrom = (k % 2 === 0) ? base : base*Z;
      var sTo   = (k % 2 === 0) ? base*Z : base;
      sp.setValueAtTime(t, [sFrom, sFrom]);
      sp.setValueAtTime(endT, [sTo, sTo]);
      log("scene"+(k+1)+" "+t+"-"+endT);
      t=endT;
    }
    log("DONE layers="+comp.numLayers+" "+comp.width+"x"+comp.height+" dur="+comp.duration);
  }
} catch(e){ try{logf.open("a"); logf.writeln("EXC "+e.toString()+" line "+(e.line||"?")); logf.close();}catch(e2){} }
