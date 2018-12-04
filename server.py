#coding=utf-8
from pymongo import MongoClient
import bottle
from bottle import *
import json,re,requests
import sys, os, time, ljqpy
from pymongo import  MongoClient
from flask import Flask, render_template as template, request, send_from_directory
import label as ll

# label=CorpusLabeling(80,stopword='停用词.txt')

config={
	'file':'corpus'
}
class labeling_system:
	def __init__(self,stopword=''):
		self.file_path='corpus'
		self.raw_article={}
		self.keywords=[]
		self.label=[]
		if type(stopword) is type([]):
			self.stopword = stopword
		elif type(stopword) is type(''):
			self.stopword = [' ','\r\n','\r','\n','\t','\u3000']
			if os.path.exists(stopword):
				self.stopword += ljqpy.LoadList(stopword)
			else:
				print('stopword path not exists')
	def collect_raw_article(self):
		file_collection=set(os.listdir(self.file_path))
		# for each in self.raw_article:
		# 	if self.raw_article[each]['title'] not in file_collection:self.raw_article.pop(each.title)
		for each in file_collection:
			if each not in self.raw_article:
				content=ll.open_text(self.file_path+'/'+each)
				info=ll.Article(each,content,self.stopword).information
				info['join_keyword']=False
				info['analysed']=False
				self.raw_article[each]=info

	# def search(self,search_type='all',page=0):



ss=labeling_system(stopword='停用词.txt')
ss.collect_raw_article()
# app=bottle.Bottle()
app = Flask(__name__, template_folder='views', static_folder='static')

@app.route('/assets/<path:filename>')
def simage(filename): return send_from_directory('assets/', filename)

@app.route('/<path:filename>')
def htmls(filename):
	try:
		return template(filename)
	except:
		pass

@app.route("/overall")
def overall():
	ss.collect_raw_article()
	res={'article_count':len(ss.raw_article),'keyword_count':len(ss.keywords),'label_count':len(ss.label)}
	return json.dumps(res,ensure_ascii=False)

@app.route("/")
def index():
	return template('index.html')

@app.route("/list_articles")
def list_articles():
	page=request.values.get('page',-1)
	tmp=[{'title':i['title'],'pub_time':i['pub_time'],'join_keyword':i['join_keyword'],'analysed':i['analysed']} for i in ss.raw_article.values()]
	tmp=sorted(tmp,key=lambda x:x.get('pub_time'))
	if page==-1:
		res=tmp
	else:
		res=tmp[(page-1)*20:page*20]
	print(tmp)
	return json.dumps(res,ensure_ascii=False,indent=4)

@app.route("/search_article")
def search_article():
	search_keyword_title=request.values.get('title','')
	print(search_keyword_title)
	print(ss.raw_article.get(search_keyword_title,{}))
	if search_keyword_title not in ss.raw_article:
		res={}
	else:
		tmp=ss.raw_article[search_keyword_title]
		res={
		'title':tmp.get('title',''),
		'text':tmp.get('text',''),
		'pub_time':tmp.get('pub_time',''),
		'label_weight':tmp.get('label_weight'),
		'abstract':tmp.get('abstract','')
		}
	return json.dumps(res,ensure_ascii=False,indent=4)

app.run(host='0.0.0.0', port=20111)