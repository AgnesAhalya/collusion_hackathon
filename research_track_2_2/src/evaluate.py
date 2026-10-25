"""Metric calculation, plotting, and per-case prediction helpers."""
import csv, json
from pathlib import Path
def metrics(labels: list[int], preds: list[int]) -> dict:
    if len(labels) != len(preds): raise ValueError("labels/predictions length mismatch")
    tp=sum(y==1 and p==1 for y,p in zip(labels,preds)); tn=sum(y==0 and p==0 for y,p in zip(labels,preds)); fp=sum(y==0 and p==1 for y,p in zip(labels,preds)); fn=sum(y==1 and p==0 for y,p in zip(labels,preds)); n=tp+tn+fp+fn
    div=lambda a,b: a/b if b else None
    return {"accuracy":div(tp+tn,n),"precision":div(tp,tp+fp),"recall":div(tp,tp+fn),"false_positive_rate":div(fp,fp+tn),"tp":tp,"tn":tn,"fp":fp,"fn":fn,"n_valid":n}

def prediction(score: float, threshold: float = 0.5) -> int:
    if not 0 <= score <= 1 or not 0 <= threshold <= 1: raise ValueError("score and threshold must be within [0,1]")
    return int(score >= threshold)

def save_results(records: list[dict], outdir: Path) -> None:
    """Write metrics/predictions and charts. Failed calls remain excluded."""
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir/"predictions.csv").open("w", newline="") as f:
        w=csv.DictWriter(f,fieldnames=["trajectory_id","dataset_type","condition","label","score","prediction","status","error","prompt_sha256"]); w.writeheader(); w.writerows(records)
    summary=[]
    for condition in ("M1","M2","M3","M4"):
        good=[r for r in records if r["condition"]==condition and r["status"]=="ok"]
        summary.append({"condition":condition,**metrics([r["label"] for r in good],[r["prediction"] for r in good])})
    with (outdir/"metrics.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    for metric, filename, title in (("accuracy","accuracy.svg","Accuracy"),("false_positive_rate","false_positive_rate.svg","False positive rate")):
        vals=[x[metric] if x[metric] is not None else 0 for x in summary]
        _bar_svg(outdir/filename,[x["condition"] for x in summary],vals,title)
    for condition in ("M1","M2","M3","M4"):
        rows=[r for r in records if r["condition"]==condition and r["status"]=="ok"]
        m=metrics([r["label"] for r in rows],[r["prediction"] for r in rows])
        _matrix_svg(outdir/f"confusion_{condition}.svg",condition,[[m["tn"],m["fp"]],[m["fn"],m["tp"]]],m["n_valid"])

def _bar_svg(path: Path, labels: list[str], values: list[float], title: str) -> None:
    x0,y0,w,h=70,55,490,260
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="390" viewBox="0 0 640 390"><rect width="100%" height="100%" fill="white"/><text x="320" y="30" text-anchor="middle" font-family="sans-serif" font-size="20">{title}</text>']
    for tick in range(6):
        y=y0+h-tick*h/5; parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+w}" y2="{y:.1f}" stroke="#ddd"/><text x="{x0-12}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{tick/5:.1f}</text>')
    bw=70; gap=(w-len(labels)*bw)/(len(labels)+1)
    for i,(label,value) in enumerate(zip(labels,values)):
        x=x0+gap+(bw+gap)*i; bh=max(0,min(1,value))*h; y=y0+h-bh
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw}" height="{bh:.1f}" fill="#3976a8"/><text x="{x+bw/2:.1f}" y="{y0+h+22}" text-anchor="middle" font-family="sans-serif" font-size="14">{label}</text><text x="{x+bw/2:.1f}" y="{max(y-6,48):.1f}" text-anchor="middle" font-family="sans-serif" font-size="12">{value:.3f}</text>')
    parts.append('</svg>'); path.write_text("".join(parts))

def _matrix_svg(path: Path, condition: str, matrix: list[list[int]], n: int) -> None:
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="400" viewBox="0 0 480 400"><rect width="100%" height="100%" fill="white"/><text x="240" y="32" text-anchor="middle" font-family="sans-serif" font-size="20">{condition} confusion matrix (n={n})</text>']
    parts += ['<text x="265" y="74" text-anchor="middle" font-family="sans-serif">Predicted</text>', '<text x="32" y="210" transform="rotate(-90 32 210)" text-anchor="middle" font-family="sans-serif">Actual</text>']
    for row in range(2):
        for col in range(2):
            x,y=125+col*140,100+row*115; shade=245-min(150,matrix[row][col]*15)
            cell_label=[["True negative","False positive"],["False negative","True positive"]][row][col]
            parts.append(f'<rect x="{x}" y="{y}" width="130" height="105" fill="rgb({shade},{shade+5 if shade<250 else 250},255)" stroke="#555"/><text x="{x+65}" y="{y+44}" text-anchor="middle" font-family="sans-serif" font-size="14">{cell_label}</text><text x="{x+65}" y="{y+78}" text-anchor="middle" font-family="sans-serif" font-size="22">{matrix[row][col]}</text>')
    parts += ['<text x="190" y="350" text-anchor="middle" font-family="sans-serif">negative</text>','<text x="330" y="350" text-anchor="middle" font-family="sans-serif">positive</text>','</svg>']; path.write_text("".join(parts))
