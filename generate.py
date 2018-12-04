import json,random
import requests
def get_attribute(word):
	apikey='ljqljqljq'
	url1='http://shuyantech.com/api/cndbpedia/ment2ent?q=%s&apikey=%s'%(word,apikey)
	try:
		res=requests.get(url1).json()
	except Exception as e:
		print(e)
		print('error')
		return None
	if res.get('ret')!=[]:
		entity=res.get('ret')[0]
	else:
		return None
	url2='http://shuyantech.com/api/cndbpedia/avpair?q=%s&apikey=%s'%(word,apikey)
	res=requests.get(url2).json()
	print(res)
get_attribute('经济')

def generate():
	with open('json/label.json','r',encoding='utf-8') as f1:
		label=json.load(f1)
	with open('json/article.json','r',encoding='utf-8') as f2:
		article=json.load(f2)
	entity={}
	for each in label:
		entity[each]={'type':['label'],'description':' '.join(label[each]),'pic_add':''}
	for each in article:
		entity[each['title']]={'type':['article'],'description':each['pub_time']+'   '+' '.join(each['words']),'pic_add':''}
	with open('result/entity.json','w',encoding='utf-8') as f:
		json.dump(entity,f,ensure_ascii=False,indent=4)
	dic={}
	triples=[]
	def clean(s):
		return s.replace('+','')



	for fa in label:
		for so in label[fa]:
			triples.append((fa,'child',so,str(int(random.random()*10))))
			triples.append((so,'father',fa,str(int(random.random()*10))))
	for each in article:
		title=each['title']
		for ll in each['label']:
			triples.append((title,'label',ll,str(int(each['label'][ll]*20))))
			if ll not in dic:dic[ll]={}
			dic[ll][title]=each['pub_time']
	for each in dic:
		for k,art in enumerate(sorted(dic[each],key=lambda x:dic[each].get(x),reverse=True)[:10]):
			triples.append((each,'article',art,str(k)))
	with open('result/entitytriples.txt','w',encoding='utf-8') as fw:
		fw.write('\n'.join(['\t'.join(i) for i in triples]))


				