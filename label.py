from pymongo import MongoClient
import ljqpy
import random,re,math,json,os,chardet,jieba
from sklearn import svm,datasets
from jieba import posseg
from datetime import datetime

config = {
	'fragment_size':1000,
	'client':'localhost',
	'host':27017,
	'collection':'nonglin4',
	'idf':{
		'client':'localhost',
		'host':27017,
		'collection':'idf',
		}
}


def text_word(word,isEnglish):
	if isEnglish:
		if word=='':return True
		if '.' in word:return False
		if word[0]=="'" or word[-1]=="'":return False
		if len(re.findall(r'[a-zA-Z]',word))==0:return False
		if word[-1] in [str(i) for i in range(10)]:return False
		return True
	else:
		tag = ' '.join([i.flag for i in posseg.cut(word)])
		if len(word) == 1: return False  #单个字
		if word[0] in['年','月'] or word[-1] in ['年','月'] and len(re.findall(r'[0-9]',word)) > 0: return False  #首个字是年月并且包含数字
		if word[-1] in [str(i) for i in range(10)]: return False   #末尾是数字
		if tag in ['m','d']: return False   #单个动词、数词、副词
		if len(re.findall(r'[\u4e00-\u9fa5a-zA-Z]',word)) == 0: return False   #不包含汉字或字母
		return True

def open_text(path):  #输入文件目录，输出文本
	with open(path, 'rb') as f: data = f.read()
	enc = chardet.detect(data)
	if enc['encoding']==None:return ''
	data = data.decode(encoding=enc['encoding'], errors='ignore')
	return data

def  fragment(fragment_index,sentences,stopword,isEnglish=False):
	fragment_index=fragment_index
	text='\n'.join(sentences)
	dirty={}
	sens=[]
	if isEnglish:
		for sen in sentences:
			sen=re.sub(r'[<>,"\'\/\\=\(\”\“\)\:\]\[\{\}]',' | ',sen)
			# tmp=[i.strip() if i.strip() not in stopword and text_word(i,True) else '|' for i in re.findall(r'[a-zA-Z\'0-9\-]*',sen)]
			tmp=[i.strip() if i.strip() not in stopword and text_word(i,True) else '|' for i in sen.split(' ')]
			while '' in tmp: tmp.remove('')
			if tmp.count('|')==len(tmp):continue
			sens.append(tmp)
	else:
		for sen in sentences:
			tmp=[word if word not in stopword and text_word(word,False) else '|' for word in jieba.cut(sen)]
			if tmp.count('|')==len(tmp):continue
			sens.append(tmp)
	tmp={'fragment_index':fragment_index,'text':text,'dirty':dirty,'sens':sens}
	return tmp



class Article:
	def __init__(self,title,ftext,stopword):
		self.text = ftext
		self.title = title
		self.stopword=stopword
		self.isEnglish=False
		self.text=self.text.lower()
		pub_time_search=re.findall(r'发布时间：[0-9]{4}\-[0-9]{2}\-[0-9]{2}',self.text)
		if len(pub_time_search)==0:
			date=datetime.now()
			date=str(date.year*10000+date.month*100+date.day)
			self.pub_time='%s-%s-%s'%(date[:4],date[4:6],date[6:])
		else:
			self.pub_time=pub_time_search[0].replace('发布时间：','')
		if len(re.findall(r'[\u4e00-\u9fa5a]',self.text))>0.2*len(self.text):
			sens=re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,}',self.text)
		else:
			sens=re.split(r'[.?!](?![0-9])',self.text)
			while '' in sens:sens.remove('')
			self.isEnglish=True
			#英文分句
		fragment_num=max(1,int(len(self.text)/config['fragment_size']))
		fragments=[]
		for i in range(fragment_num):
			ss=int(len(sens)/fragment_num*i)
			se=int(len(sens)/fragment_num*(i+1))
			fragments.append(fragment(i,sens[ss:se],self.stopword,self.isEnglish))
		self.fragments=fragments
		self.information={
			'title':self.title,
			'text':self.text,
			'isEnglish':self.isEnglish,
			'pub_time':self.pub_time,
			'fragments':self.fragments
		}


# stopword = [' ','\r\n','\r','\n','\t','\u3000']
# stopword += ljqpy.LoadList('停用词.txt')

# title='“跟习近平学领导艺术”系列全集[2014-07-11].txt'
# corpus=open_text('corpus/'+title)
# Article=Article(title,corpus,stopword)
