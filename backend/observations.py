"""Real per-analysis-frame counts. Observations are not unique-worker counts."""

def record_observation(db, workers, source, model):
    row=model(source=source, workers=len(workers),
        compliant=sum(w['status']=='COMPLIANT' for w in workers),
        violating=sum(w['status']=='VIOLATION' for w in workers),
        unknown=sum(w['status']=='NOT_ASSESSABLE' for w in workers),
        mask_unknown=sum(w.get('mask_assessment')=='not assessable' for w in workers))
    db.add(row)
    return row
