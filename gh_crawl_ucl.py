# -*- coding: utf-8 -*-
"""GitHub Actions 欧冠补采: 从GitHub美国IP抓取(每次运行=新IP, 绕过WAF)
1) PC赛程页(阶段+全部) 拿所有比赛(含23/24)
2) www AJAX 拿10项赔率
3) 写CSV到 data/ 目录
"""
import io, os, re, json, time, csv, sys
from curl_cffi import requests as creq

BASE = "https://www.okooo.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0"
SEASONS = [("14801", "23-24"), ("110139", "24-25"), ("110411", "25-26"), ("110674", "26-27")]
PROVIDERS = [
    ("99家平均初赔", 24, 1), ("竞彩初赔", 2, 1), ("澳门初赔", 84, 1), ("bet365初赔", 27, 1),
    ("威廉希尔初赔", 14, 1), ("立博初赔", 82, 1), ("Interwetten初赔", 43, 1),
    ("bet365初盘", 27, 2), ("澳门初盘", 84, 2), ("伟德初盘", 65, 2),
]
OUT = "data"
os.makedirs(OUT, exist_ok=True)

def get(url, referer=None):
    h = {"User-Agent": UA}
    if referer:
        h["Referer"] = referer
    for i in range(5):
        try:
            r = creq.get(url, impersonate="chrome", headers=h, timeout=25)
            body = r.text[:2000]
            print("  [GET %s] status=%s len=%s" % (url[:80], r.status_code, len(r.content)), flush=True)
            if r.status_code == 200 and "aliyun_waf" not in body:
                return r.text
        except Exception as e:
            print("  [GET %s] 异常 %s" % (url[:60], str(e)[:60]), flush=True)
        time.sleep(8)
    return None

def get_mobile_matches(month):
    """移动版月份页兜底: 返回match列表(仅最近3季)"""
    h = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"}
    url = "https://m.okooo.com/saishi/7-%s/" % month
    try:
        r = creq.get(url, headers=h, timeout=25)
        s = r.content.decode("gbk", "replace")
    except Exception:
        return []
    rows = []
    for m in re.finditer(r'MatchID=(\d+)', s):
        mid = m.group(1)
        seg = s[max(0, m.start()-800):m.end()+400]
        teams = re.findall(r'class="team"[^>]*>([^<]+)</a>', seg)
        date = re.findall(r'class="title">(\d{4}-\d{2}-\d{2})</div>', s[:m.start()])
        lunci = re.findall(r'class="lunci"[^>]*>([^<]+)</a>', seg)
        season = "?"
        lm = re.search(r'lunci-[\d]+-(\d+)-', seg)
        if lm:
            season = lm.group(1)
        if len(teams) >= 2:
            rows.append({"matchid": mid, "round": lunci[0].strip() if lunci else "", "time": date[-1] if date else "",
                         "home": teams[0].strip(), "score": "", "away": teams[1].strip(), "season": season, "label": ""})
    return rows

def get_rounds(league_id, season_id):
    """PC赛程页: 联赛轮次 + 杯赛阶段全部"""
    html = get(BASE + "/soccer/league/%d/schedule/%s/" % (league_id, season_id), BASE + "/soccer/league/7/")
    if not html:
        return []
    rounds = []
    for p in re.findall(r'/soccer/league/%d/schedule/%s/([0-9-]+)/' % (league_id, season_id), html):
        if "-" in p and not p.endswith("-"):
            rounds.append(p)
    for link in re.findall(r'/soccer/league/%d/schedule/%s/([0-9]+-[0-9]+/\?show=all)' % (league_id, season_id), html):
        rounds.append(link)
    stages = set(re.findall(r'/soccer/league/%d/schedule/%s/(\d+)/' % (league_id, season_id), html))
    for st in sorted(stages, key=int):
        sh = get(BASE + "/soccer/league/%d/schedule/%s/%s/" % (league_id, season_id, st), BASE + "/soccer/league/7/")
        if sh:
            for link in re.findall(r'/soccer/league/%d/schedule/%s/([0-9]+-[0-9]+/\?show=all)' % (league_id, season_id), sh):
                rounds.append(link)
    return sorted(set(rounds))

def parse_round(league_id, season_id, rp):
    html = get(BASE + "/soccer/league/%d/schedule/%s/%s" % (league_id, season_id, rp), BASE + "/soccer/league/7/")
    if not html or "team_fight_table" not in html:
        return []
    rows = []
    for tr in re.findall(r'<tr matchid="(\d+)"[^>]*>(.*?)</tr>', html, re.S):
        mid, body = tr
        tds = re.findall(r'<td[^>]*>(.*?)</td>', body, re.S)
        if len(tds) < 5:
            continue
        def clean(x):
            return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', x)).strip()
        rows.append({"matchid": mid, "round": clean(tds[1]), "time": clean(tds[0]),
                     "home": clean(tds[2]), "score": clean(tds[3]), "away": clean(tds[4])})
    return rows

def odds_for(mids, pid, bt):
    url = BASE + "/ajax/?method=data.match.odds&matchIds=%s&providerId=%d&bettingTypeId=%d" % (",".join(mids), pid, bt)
    raw = get(url, BASE + "/soccer/league/8/")
    try:
        return json.loads(raw) if raw and raw.strip().startswith("{") else {}
    except Exception:
        return {}

def main():
    all_matches = []
    for sid, label in SEASONS:
        rounds = get_rounds(7, sid)
        print("赛季%s: %d个轮次/阶段" % (label, len(rounds)), flush=True)
        for rp in rounds:
            ms = parse_round(7, sid, rp)
            for m in ms:
                m["season"] = sid
                m["label"] = label
            all_matches.extend(ms)
    print("PC赛程页共找到 %d 场比赛" % len(all_matches), flush=True)
    # 移动版兜底(3季7月+8月资格赛)
    for month in ["2024-07", "2024-08", "2025-07", "2025-08", "2026-07", "2026-08"]:
        ms = get_mobile_matches(month)
        print("移动版 %s: %d 场" % (month, len(ms)), flush=True)
        all_matches.extend(ms)
    # 去重
    seen, dedup = set(), []
    for m in all_matches:
        if m["matchid"] not in seen:
            seen.add(m["matchid"])
            dedup.append(m)
    all_matches = dedup
    print("去重后共 %d 场比赛" % len(all_matches), flush=True)
    # 写诊断报告(强制提交, 便于排查)
    with io.open("report.txt", "w", encoding="utf-8") as f:
        f.write("matches: %d\n" % len(all_matches))
        for m in all_matches[:20]:
            f.write("%s|%s|%s|%s|%s|%s\n" % (m.get("season"), m.get("time"), m.get("home"), m.get("score"), m.get("away"), m.get("matchid")))
    # 写CSV(每赛季每类型)
    for pname, pid, bt in PROVIDERS:
        kind = "初赔" if bt == 1 else "初盘"
        by_season = {}
        for m in all_matches:
            by_season.setdefault(m["season"], []).append(m)
        for sid, ms in by_season.items():
            path = os.path.join(OUT, "欧冠(7)_%s_%s.csv" % (kind, sid))
            existing = set()
            if os.path.exists(path):
                for row in csv.DictReader(io.open(path, encoding="utf-8-sig", errors="replace")):
                    existing.add((row.get("时间",""), row.get("主队",""), row.get("客队",""), row.get("机构","")))
            f = io.open(path, "a", encoding="utf-8-sig", newline="")
            w = csv.writer(f)
            if not existing:
                w.writerow(["联赛","赛季","轮次","时间","主队","比分","客队","机构","主胜","平","客胜","上盘水位","盘口","下盘水位","让球值"])
            for i in range(0, len(ms), 10):
                chunk = ms[i:i+10]
                od = odds_for([m["matchid"] for m in chunk], pid, bt)
                for m in chunk:
                    vals = od.get(m["matchid"], [])
                    key = (m["time"], m["home"], m["away"], pname)
                    if key in existing:
                        continue
                    existing.add(key)
                    row = ["欧冠", m["season"], m["round"], m["time"], m["home"], m["score"], m["away"], pname]
                    if bt == 1 and len(vals) >= 3:
                        row += [vals[0], vals[1], vals[2], "", "", "", ""]
                    elif bt == 2 and len(vals) >= 4:
                        row += ["", "", "", "", vals[0], vals[1], vals[2], vals[3]]
                    else:
                        row += ["", "", "", "", "", "", "", ""]
                    w.writerow(row)
            f.close()
    # 摘要
    n = 0
    for fp in os.listdir(OUT):
        if fp.endswith(".csv"):
            n += sum(1 for _ in csv.DictReader(io.open(os.path.join(OUT, fp), encoding="utf-8-sig", errors="replace")))
    print("本次运行后 data/ 共 %d 行" % n, flush=True)

if __name__ == "__main__":
    main()
