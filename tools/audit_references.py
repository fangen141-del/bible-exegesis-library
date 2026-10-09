"""Recheck every stored link without confusing omitted translation verses with bad numbers.
Usage: python tools/audit_references.py /path/to/commentary.sqlite
Rewrites only catalog metadata; body IDs and search postings remain unchanged.
"""
import sqlite3,json,gzip,pathlib,sys,re,collections,os
root=pathlib.Path(__file__).resolve().parents[1]; out=root/'dist' if (root/'dist').exists() else root; db=sqlite3.connect('file:'+str(pathlib.Path(sys.argv[1]).resolve())+'?mode=ro',uri=True)
cat=json.loads(gzip.decompress((out/'data/catalog.gz').read_bytes()))
limits={(b,c):v for b,c,v in db.execute('select book,chapter,max(verse) from canon group by book,chapter')}
links=collections.defaultdict(list); errors=[]; relations=collections.Counter()
for did,b,ch,start,end,relation in db.execute('select * from scripture_links'):
 relations[relation]+=1
 if (b,ch) not in limits or start<0 or end<start or end>limits.get((b,ch),0):errors.append([did,b,ch,start,end,relation]);continue
 links[did].append([b,ch,start,end,relation])
checks=collections.Counter(); title_errors=[]
for i,(did,kind,title,scope) in enumerate(db.execute('select id,kind,title,scope from documents order by rowid')):
 d=cat['documents'][i]; assert d[1]==title
 d[5]=links[did];d[6:]=[scope,'upstream-structured' if kind in ('commentary','sermon') and scope!='原v1.5样本' else 'legacy-unreviewed' if scope=='原v1.5样本' else 'citation-extracted']
 if kind=='commentary' and scope!='原v1.5样本' and d[5]:
  match=re.search(r' · (\w+) (\d+):(\d+)(?:-(\d+))?$',title)
  if match:
   expected=[match[1],int(match[2]),int(match[3]),int(match[4] or match[3])]
   if not any(r[0]==expected[0] and r[1]==expected[1] and r[2]==expected[2] and (not match[4] or r[3]==expected[3]) for r in d[5]):title_errors.append([did,title,d[5]])
   else:checks['commentary_title_matches']+=1
  else:checks['commentary_other_heading']+=1
 checks[kind]+=1
cat['chapter_limits']={b:{str(ch):v for (bb,ch),v in limits.items() if bb==b} for b in set(b for b,ch in limits)}
cat['reference_audit']={'checked_links':sum(relations.values()),'invalid_numeric_links':len(errors),'title_mismatches':len(title_errors),'method':'数字范围及原始注释标题一致性检查；上游讲章主讲标记与书籍引用分开；不代表人工逐篇校订。'}
tmp=out/'data/catalog.new.gz';tmp.write_bytes(gzip.compress(json.dumps(cat,ensure_ascii=False,separators=(',',':')).encode(),compresslevel=6));os.replace(tmp,out/'data/catalog.gz')
report={'date':'2026-10-09','checks':dict(checks),'relations':dict(relations),**cat['reference_audit'],'invalid_links':errors,'title_mismatch_records':title_errors,'limitations':['未进行135983篇正文逐篇人工核对','讲章主讲经文来自上游结构化字段，尚未逐篇校订','书籍关联来自自动引用提取，只能作为引用线索','旧版7条样本待复核，默认直接释义搜索不收录','BSB缺节不能判为非法节号，范围按各章最大节号检查']}
(out/'reference-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False)[:2500])
