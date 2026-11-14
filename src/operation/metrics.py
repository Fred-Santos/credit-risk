"""Métricas operacionais: relógio monotônico, contadores e amostragem Linux."""
import os
import threading
import time


class StageClock:
    def __init__(self, clock=time.perf_counter):
        self.clock=clock;self.started=clock();self.last=self.started;self.name=None;self.intervals=[]

    def enter(self, name):
        current=self.clock()
        if self.name is not None:
            self.intervals.append({'stage':self.name,'duration_seconds':current-self.last})
        elif current>self.last:
            self.intervals.append({'stage':'unattributed','duration_seconds':current-self.last})
        self.name=name;self.last=current

    def snapshot(self):
        current=self.clock()
        intervals=list(self.intervals)
        intervals.append({'stage':self.name or 'unattributed','duration_seconds':current-self.last})
        stages={}
        for item in intervals:stages[item['stage']]=stages.get(item['stage'],0)+item['duration_seconds']
        return {'total_seconds':current-self.started,'stage_seconds':stages,'intervals':intervals,
                'clock':'time.perf_counter','scope':'exclusive wall time; includes Spark actions and validation within each stage'}


def batch_counters(batches):
    fields=('input_deliveries','duplicate_deliveries','superseded_revisions','inserts','updates',
            'ignored_same_revision','ignored_older_revision')
    tables={}
    for batch in batches:
        for name,metrics in batch['metrics'].items():
            values=tables.setdefault(name,{key:0 for key in fields})
            for key in fields:values[key]+=metrics[key]
    return {'completed_batches':len(batches),'tables':tables,
        'rejected_rows':0,'scope':'completed, approved batches only; inserts/updates are checked against Delta commits; deliveries are not distinct business keys'}


def publication_inventory(client, manifest):
    tables={}
    for name,entry in manifest['tables'].items():
        sizes=client.list(entry['key']+'/')
        files={key:size for key,size in sizes.items() if not key.endswith('/')}
        tables[name]={'rows':entry['rows'],'files':len(files),'objects':len(sizes),
            'directory_markers':len(sizes)-len(files),'logical_bytes':sum(sizes.values()),
            'parquet_files':sum(key.endswith('.parquet') for key in files),
            'delta_log_files':sum('/_delta_log/' in key for key in files)}
    return {'tables':tables,'total_files':sum(t['files'] for t in tables.values()),
            'total_objects':sum(t['objects'] for t in tables.values()),
            'total_logical_bytes':sum(t['logical_bytes'] for t in tables.values()),
            'scope':'all objects in selected publication prefixes, including retained versions; not physical disk blocks or newly written bytes'}


class ResourceSampler:
    def __init__(self, interval=0.5):
        self.interval=interval;self.stop_event=threading.Event();self.peak=0;self.samples=0
        self.cost=0.;self.errors=[];self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start();return self

    def _run(self):
        from scripts.measure_resources import process_tree_rss
        while not self.stop_event.is_set():
            started=time.perf_counter()
            try:self.peak=max(self.peak,process_tree_rss(os.getpid()));self.samples+=1
            except Exception as error:self.errors.append(type(error).__name__)
            self.cost+=time.perf_counter()-started
            self.stop_event.wait(self.interval)

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:self.thread.join()
        return {'peak_process_tree_rss_bytes':self.peak,'samples':self.samples,
            'interval_seconds':self.interval,'sampling_work_seconds':self.cost,'errors':self.errors,
            'scope':'Linux process and descendants, including Spark and service started here; pre-existing service excluded; shared pages may be counted twice; short peaks may be missed'}
