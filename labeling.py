from pymongo import MongoClient
import ljqpy
import random,re,math,json,os,chardet,jieba
from sklearn import svm,datasets
from jieba import posseg
from datetime import datetime
# from sklearn.externals import joblib

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

def open_text(path):  #输入文件目录，输出文本
	with open(path, 'rb') as f: data = f.read()
	enc = chardet.detect(data)
	if enc['encoding']==None:return ''
	data = data.decode(encoding=enc['encoding'], errors='ignore')
	return data

def make_key(a,b):
	if a > b: return a+'&'+b
	else: return b+'&'+a

def get_gap(lst):
	# word=' '.join(lst)
	# if len(re.findall('[\u4e00-\u9fa5]',word))==0:return ' '
	return '+'

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

db2=MongoClient(config['idf']['client'],config['idf']['host'])[config['idf']['collection']]
global_idf={}
def search_global_idf(word):
	if word in global_idf:return global_idf[word]
	search=db2['idf'].find({'word':word})
	if search.count()==0:
		ans=16
	else:
		ans=search[0].get('idf')
	global_idf[word]=ans
	return ans

class Fragment:
	def __init__(self,fragment_index,sentences,stopword=[],isEnglish=False):
		self.fragment_index=fragment_index
		self.text='\n'.join(sentences)
		self.dirty={}
		self.sens=[]
		if isEnglish:
			for sen in sentences:
				sen=re.sub(r'[<>,"\'\/\\=\(\”\“\)\:\]\[\{\}]',' | ',sen)
				# tmp=[i.strip() if i.strip() not in stopword and text_word(i,True) else '|' for i in re.findall(r'[a-zA-Z\'0-9\-]*',sen)]
				tmp=[i.strip() if i.strip() not in stopword and text_word(i,True) else '|' for i in sen.split(' ')]
				while '' in tmp: tmp.remove('')
				if tmp.count('|')==len(tmp):continue
				self.sens.append(tmp)
		else:
			for sen in sentences:
				tmp=[word if word not in stopword and text_word(word,False) else '|' for word in jieba.cut(sen)]
				if tmp.count('|')==len(tmp):continue
				self.sens.append(tmp)

class Article:
	def __init__(self,ftext,title,start_index,stopword):
		self.text = ftext
		self.title = title
		self.start_index = start_index
		self.stopword=stopword
		self.isEnglish=False
		self.text=self.text.lower()
		pub_time_search=re.findall(r'发布时间：[0-9]{4}\-[0-9]{2}\-[0-9]{2}',self.text)
		if len(pub_time_search)==0:
			date=datetime.now()
			date=str(date.year*10000+date.month*100+datetime)
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
		self.fragments=[]
		for i in range(fragment_num):
			ss=int(len(sens)/fragment_num*i)
			se=int(len(sens)/fragment_num*(i+1))
			self.fragments.append(Fragment(start_index+i,sens[ss:se],self.stopword,self.isEnglish))

class CorpusLabeling:
	def __init__(self,min_limit,stopword=''):
		self.min_limit=min_limit
		if type(stopword) is type([]):
			self.stopword = stopword
		elif type(stopword) is type(''):
			self.stopword = [' ','\r\n','\r','\n','\t','\u3000']
			if os.path.exists(stopword):
				self.stopword += ljqpy.LoadList(stopword)
			else:
				print('stopword path not exists')

		self.fragment_count=0
		self.documents=[]
		self.label={}
		self.article=[]
		self.keyword_docs=[]
		self.collect_arw_article()

	def init_from_documents(self, file_sets, save_in_mongo=False , save_in_json=False):
		self.keyword = {}
		self.documents = []
		next_index=0
		if type(file_sets)==type([]):
			for file in file_sets:
				# try:
				ftext=file['text']
				title=file['id']
				print(title)
				document=Article(ftext,title,next_index,self.stopword)
				self.documents.append(document)
				next_index+=len(document.fragments)
				# except:
				# 	print('error',title)

		elif type(file_sets)==type(' '):
			for file in os.listdir(file_sets):
				try:
					fn = os.path.join(file_sets, file)
					print(fn)
					ftext = open_text(fn)
					document = Article(ftext, file, next_index, self.stopword)
					self.documents.append(document)
					next_index+=len(document.fragments)
				except:
					print('bad')
					pass
		self.fragment_count=next_index
		if save_in_json:
			self.dirty=[]
			for document in self.documents:
				cur_article={}
				cur_article['pub_time']=document.pub_time
				cur_article['title']=document.title
				cur_article['start_index']=document.start_index
				cur_article['fragments']=[]
				for frag in document.fragments:
					cur_article['fragments'].append({'fragment_index':frag.fragment_index,'sens':frag.sens})
				self.dirty.append(cur_article)
			with open('json/dirty.json','w',encoding='utf-8')as f:
				json.dump(self.dirty,f,ensure_ascii=False,indent=4)


	def init_from_json(self,reconstruct=False):
		need_to_load=[]
		if os.path.exists(r'json\\dirty.json')==False or reconstruct==True:
			print('nothing to load, we will construct the system from the corpus')
			self.init_from_documents('corpus',save_in_json=True)
			with open('json/dirty.json','r',encoding='utf-8')as f:
				self.documents=json.loads(''.join(f.readlines()))
			self.fragment_count=sum([len(i['fragments']) for i in self.documents])
			f.close()
		else:
			with open('json/dirty.json','r',encoding='utf-8')as f:
				self.documents=json.loads(''.join(f.readlines()))
			self.fragment_count=sum([len(i['fragments']) for i in self.documents])
			f.close()
			already=set([i['title'] for i in self.documents])
			print('there are %d articles already'%len(already))
			corpus=[]
			for i in os.listdir('corpus'):
				if 'txt' in i:corpus.append(i)
			need_to_load=list(set(corpus)-set(already))
			print('there are %d articles to be loaded' %len(need_to_load))
			if len(need_to_load)>len(corpus)/5:
				reconstruct=True
				print('too much articles are not loaded, we will reconstruct the system')
				self.init_from_documents('corpus',save_in_json=True)
		if os.path.exists('json/keyword.json') and reconstruct!=True:
			with open('json/keyword.json','r',encoding='utf-8') as f:
				tmp=json.loads(''.join(f.readlines()))
			self.keyword_docs=tmp['doc']
			self.parents=tmp['parents']
			self.children=tmp['children']
			self.synonym=tmp['synonym']
			f.close()
		else:
			self.init_keywords(self.min_limit)
			tmp={'doc':self.keyword_docs,'parents':self.parents,'children':self.children,'synonym':self.synonym}
			with open('json/keyword.json','w',encoding='utf-8')as f:
				json.dump(tmp,f,ensure_ascii=False,indent=4)
		if os.path.exists('json/label.json') and reconstruct!=True:
			with open('json/label.json','r',encoding='utf-8') as fr:
				self.label=json.loads(''.join(fr.readlines()))
		else:
			self.create_labels()
		return need_to_load

	def init_keywords(self,min_limit):
		if self.documents==[]:
			print('there is no documents')
			return
		synonym={}
		sens=[]
		for doc in self.documents:
			for frag in doc['fragments']:
				sens+=frag['sens']
		ngram={1:{}}
		keywords={}
		for sen in sens:
			for word in sen:
				if word =='|':continue
				ngram[1][word]=ngram[1].get(word,0)+1
		for word in list(ngram[1].keys()).copy():
			if ngram[1][word]<min_limit:ngram[1].pop(word)
		keywords.update(ngram[1])
		for length in range(2,5):
			ngram[length]={}
			for sen in sens:
				# gap=get_gap(sen)
				gap='+'
				for i in range(len(sen)-length+1):
					if '|' in sen[i:i+length]:continue
					if gap.join(sen[i:i+length-1]) not in ngram[length-1]:continue
					longword=gap.join(sen[i:i+length])
					ngram[length][longword]=ngram[length].get(longword,0)+1
			for word in list(ngram[length].keys()).copy():
				if ngram[length][word]<min_limit:
					ngram[length].pop(word)
				else:
					orinigal_word='+'.join(word.split('+')[:-1])
					if orinigal_word not in keywords:print('strange',orinigal_word)
					if ngram[length].get(word,0)>0.8*keywords.get(orinigal_word,0):
						synonym[orinigal_word]=word
			if ngram[length]=={}:break
			keywords.update(ngram[length])

		coexist={}
		self.keyword_docs={i:set() for i in keywords}
		self.children={i:set() for i in keywords}
		self.parents={i:set() for i in keywords}
		self.related={i:set() for i in keywords}
		try:
			with open('json/delete.txt','r',encoding='utf-8')as f:
				delete=set([line.strip() for line in f.readlines()])
		except Exception as e:
			print(e)
			delete=set([])

		for doc in self.documents:
			for frag in doc['fragments']:
				words={}
				for sen in frag['sens']:
					for length in range(1,5):
						for i in range(len(sen)-length):
							if '|' in sen[i:i+length]:continue
							longword='+'.join(sen[i:i+length])
							if longword not in keywords or longword in synonym or longword in delete:continue
							words[longword]=words.get(longword,0)+1
							self.keyword_docs[longword].add(frag['fragment_index'])
				frag['words']=words
				ww=list(words.keys())
				for i in range(len(ww)):
					for j in range(i+1,len(ww)):
						key=make_key(ww[i],ww[j])
						coexist[key]=coexist.get(key,0)+1

		for key in coexist:
			key_split=key.split('&')
			a,b=key_split[0],key_split[1]
			if a in synonym or b in synonym:continue
			counta=len(self.keyword_docs[a])
			countb=len(self.keyword_docs[b])
			countc=coexist[key]
			if countc/counta>0.9 and countc/countb>0.9:
				synonym[counta]=countb
			elif countc/counta>0.9:
				self.children[b].add(a)
				self.parents[a].add(b)
			elif countc/countb>0.9:
				self.children[a].add(b)
				self.parents[b].add(a)
			elif countc/counta>0.5 and countc/countb>0.5:
				self.related[a].add(b)
				self.related[b].add(a)
		self.synonym=synonym
		self.keyword_docs={i:list(self.keyword_docs[i]) for i in self.keyword_docs}
		self.children={i:list(self.children[i]) for i in self.children}
		self.parents={i:list(self.parents[i]) for i in self.parents}

	def create_labels(self,  doc_limit=None, save_in_mongo=False):
		#doc_limit 限制标签包含的最少文档数量
		def child_num(s, root=False):
			if root != True and s < 400:
				return int(s/50)
			else:
				return int(math.log(6614)/math.log(1.8))
			# magic
		def entropy(x):
			# x += 0.05
			if x <= 0 or x >= 1:return 0
			ans = x*math.log(x)+(1-x)*math.log(1-x)
			return - ans

		def value_for_word(word, father_size, count):
			size = count[word]
			if size == 0 or size >= father_size:return 0
			en1 = entropy(size/father_size)
			templst = sorted(self.children[word], key=lambda x:count[word], reverse = True)[:child_num(size)]
			lst = [entropy(count[i]/size) for i in templst]
			en2 = sum(lst)
			return en1 + en2

		def search_child(candidate, father, count, doc_limit = None):
			docs = set()
			already = []
			while candidate!=[]:
				sscore=[]
				for each in candidate:
					sscore.append(len(set(self.keyword_docs[each])-docs))
				if max(sscore)==0:break
				tar=candidate[sscore.index(max(sscore))]

				docs=docs|set(self.keyword_docs[tar])
				already.append(tar)
				candidate.remove(tar)
				if len(already)>child_num(father)*1.5:break

			if len(already)==1:return []
			return already


		def child_gene(word, count, doc_limit):
			candidates = self.children[word]
			for can in candidates.copy():
				if can not in self.keyword_label:
					candidates.remove(can)
			# candidates = sorted(candidates, key=lambda x:entropy(count[x]/count[word]), reverse = True)[:child_num(count[word])*3]
			candidates = sorted(candidates, key=lambda x:value_for_word(x,count[word],count), reverse = True)[:child_num(count[word])*2]
			# candidates = sorted(candidates, key=lambda x:value_for_word(x,count[word],count), reverse = True)[:child_num(count[word])*1.5]
			return search_child(candidates, count[word], count, doc_limit)

		def build_tree(word, count, doc_limit):
			if word in self.label_children: return
			self.label_children[word] = []
			child_get = child_gene(word, count, doc_limit)
			# print(word,child_get)
			if len(child_get) == 0: return
			self.label_children[word] = child_get
			for each in child_get:
				self.label_parents.setdefault(each, []).append(word)
			for each in child_get:
				build_tree(each,count,doc_limit)

		#clean
		#1.子包含父并且文档包含在60%以上
		#2.人工删选不合适的
		#3.包含完全相同的字
		ugly=[]
		try:
			with open('json/delete.txt','r',encoding='utf-8')as f:
				delete=[line.strip() for line in f.readlines()]
		except Exception as e:
			print(e)
			delete=[]
		count = {i:len(self.keyword_docs[i]) for i in self.keyword_docs}
		for word in self.children:
			if word in delete:
				ugly.append(word)
				continue
		for each in self.children:
			for child in self.children[each]:
				if count[child]>count[each]*0.9:ugly.append(child)
				if child ==each:continue
				if len(set(each.split('+'))-set(child.split('+')))==0 and count[child]>count[each]*0.6:
					self.children[child]=self.children[each]
					self.keyword_docs[child]=self.keyword_docs[each]
					count[child]=count[each]
					ugly.append(each)
		for each in list(self.children.keys()).copy():
			if each in ugly:
				self.children.pop(each)
		self.label_children = {'root':[]}
		self.label_parents = {'root':[]}
		# print(len(self.keyword_docs))
		self.keyword_label={}
		for each in self.children:
			if each not in self.synonym:
				self.keyword_label[each]=set(self.keyword_docs[each])
		# count = {i:len(self.keyword_docs[i]) for i in self.keyword_docs}

		self.keyword_label=sorted(self.keyword_label,key=lambda x:count[x],reverse=True)[:2000]
		root_size = self.fragment_count
		root_candi = sorted(self.keyword_label, key=lambda x:entropy(count[x]/root_size), reverse=True)[:child_num(root_size,True)*2]
		# root_candi = sorted(self.keyword_label, key=lambda x:value_for_word(x,root_size,count), reverse=True)[:child_num(root_size,True)*2]
		# root_candi
		root_child = search_child(root_candi,root_size,count,doc_limit)
		try:
			with open('json/must_in.txt','r',encoding='utf-8') as f:
				must_in=[line.strip() for line in f.readlines()]
			root_child=list(set(root_child)|set(must_in))
		except Exception as e:
			print(e)

		for child in root_child:
			self.label_children['root'].append(child)
			if child not in self.label_parents: self.label_parents[child] = []
			self.label_parents[child].append('root')
			build_tree(child, count, doc_limit)
		# print('标签生成完毕')
		# for i in self.label_children:
		# 	print(i,self.label_children[i])
		# print(len(self.label_children))
		self.label=self.label_children
		with open('json/label.json','w',encoding='utf-8')as f:
			json.dump(self.label,f,ensure_ascii=False,indent=4)

	def get_score_for_article(self,need_to_load=[]):
		if self.label=={}:
			with open('json/label.json','r',encoding='utf-8') as f:
				self.label=json.loads(''.join(f.readlines()))
			f.close()
		if self.documents==[]:
			with open('json/dirty.json','r',encoding='utf-8')as f:
				self.documents=json.loads(''.join(f.readlines()))
			self.fragment_count=sum([len(i['fragments']) for i in self.documents])
			f.close()
		if self.keyword_docs==[]:
			if os.path.exists('json/keyword.json'):
				with open('json/keyword.json','r',encoding='utf-8') as f:
					tmp=json.loads(''.join(f.readlines()))
				self.keyword_docs=tmp['doc']
				self.parents=tmp['parents']
				self.children=tmp['children']
				self.synonym=tmp['synonym']
				f.close()
		count={i:len(self.keyword_docs[i]) for i in self.keyword_docs}
		mapping={}
		for word in self.parents:
			if word in self.label:mapping[word]={word:1}
			for fa in self.parents[word]:
				if fa in self.label:
					mapping.setdefault(word,{}).update({fa:count[word]/count[fa]})

		print('%d articles will be loaded' % len(need_to_load))
		for each in need_to_load:
			fn = os.path.join('corpus', each)
			print('newarticle',fn)
			ftext = open_text(fn)
			document = Article(ftext, each, 0, self.stopword)
			cur_article={}
			cur_article['pub_time']=document.pub_time
			cur_article['title']=document.title
			cur_article['start_index']=document.start_index
			cur_article['fragments']=[]
			for frag in document.fragments:
				cur_article['fragments'].append({'fragment_index':frag.fragment_index,'sens':frag.sens})
			self.documents.append(cur_article)

		self.article=[]
		for doc in self.documents:
			tmp={}
			tmp['pub_time']=doc['pub_time']
			tmp['title']=doc['title']
			tmp['words']={}
			tmp['score']={}
			tmp['label']={}
			for frag in doc['fragments']:
				for sen in frag['sens']:
					for length in range(1,5):
						for i in range(len(sen)-length):
							if '|' in sen[i:i+length]:continue
							longword='+'.join(sen[i:i+length])
							if longword not in mapping:continue
							tmp['words'][longword]=tmp['words'].get(longword,0)+1
			for word in tmp['words']:
				tmp['score'][word]=tmp['words'][word]/sum(tmp['words'].values())*math.log(self.fragment_count/(count[word]+1))
			for word in tmp['score']:
				for each in mapping.get(word,[]):
					tmp['label'][each]=tmp['label'].get(each,0)+tmp['score'][word]*mapping[word][each]
			self.article.append(tmp)
		with open('json/article.json','w',encoding='utf-8')as f:
			json.dump(self.article,f,ensure_ascii=False,indent=4)

# if __name__=='__main__':
# 	label=CorpusLabeling(80,stopword='停用词.txt')
# 	need_to_load=label.init_from_json(reconstruct=False)
# 	label.get_score_for_article(need_to_load)

#init_form_documents 从文件中初始化,完全从零初始化
#init_from_json 从json 文件中初始化,至少要求有dirty.json,会根据是否存在keyword.json执行keyword计算函数
#get_score_for_article 为每个文件生成关键词和标签的分数,要求documents,keyword,label已经生成完毕或者保存在json文件中，生成article.json