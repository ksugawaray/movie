from src.crawler.base_crawler import BaseCrawler
from bs4 import BeautifulSoup
import pandas as pd
from pprint import pprint
import re
import json
import os
from Feature_Crawler import Feature_Crawler, load_image
from Tsv_Crawler import Tsv_Crawler
from sklearn.model_selection import KFold, train_test_split
import torchvision.transforms as transforms
from torchvision.transforms import ToTensor,Grayscale,ToPILImage
import numpy as np
import functools as ft
import itertools as it
import matplotlib.pyplot as plt
from sklearn.preprocessing import MultiLabelBinarizer
import gensim
import re
from gensim.models.doc2vec import Doc2Vec
from sklearn.model_selection import train_test_split
from math import log
from sklearn.decomposition import PCA
from torchvision import models
import torch.nn as nn
import torch

di="data/preprocessed"

def one_to_three(img):
    if img.shape[0]!=3:
        transform=transforms.Compose(
            [
                transforms.ToPILImage(),
                Grayscale(num_output_channels=3)
            ]
        )
        return transform(img)
    else:
        transform=transforms.ToPILImage()
        return transform(img)

class integrator():
    
    
    def __init__(self,start=0,last=0,order_list=None,order_name=None,movie_only=True,tsv=False,optional_data=None,not_none_col=[],target_col=None,delete_col=[],doc_embed_dim=30,image_embed_dim=30,n_splits=5,shuffle=True,di=di,combine_rate=0.07):
        """
        self.transform=transforms.Compose(
                    [
                        transforms.ToTensor(),
                        transforms.Lambda(one_to_three),
                        transforms.Resize([300,256]),
                        transforms.ToTensor()
                    ])
         """
        self.combine_rate=combine_rate
        self.doc_embed_dim=doc_embed_dim
        self.image_embed_dim=image_embed_dim
        self.di=di
        self.start=start
        self.last=last
        self.order_list=order_list
        self.order_name=order_name
        self.movie_only=movie_only
        self.tsv=tsv
        self.optional_data=optional_data
        self.delete_col=delete_col
        
        
        #不要もしくは重なるcolumn('averageRating', 'numVotes'重複, 'attributes','job'扱う方法が不明)
        self.delete_col.extend(['primaryTitle', 'originalTitle','characters','attributes','job','isAdult','averageRating', 'numVotes','image_exist','j_image_exist','description', 'domestic_money', 'international_money','title','types'])
        
        self.first_number_col=['actor','director','writers','directors','creator','nconst','parentTconst','startYear','endYear','runtimeMinutes','seasonNumber','episodeNumber','isOriginalTitle']
        self.log=['full_money','domestic_money', 'international_money','ratingCount']
        #カテゴリー onehot
        self.categorical_col=['region', 'language', 'titleType','category','contentRating']
        
        self.date=['datePublished']
        self.genre=['genres']
        
        self.word=['keywords','story_line']
        
        self.not_none_col=not_none_col
        if self.doc_embed_dim:
            self.not_none_col.extend(self.word)

        self.target_col=target_col
        
        self.preprocess_if_necessary()
        
        self._full = self.set_push_data(self.full)
        self.splitter = KFold(n_splits=n_splits, shuffle=shuffle)
        self.split_full=[[self.set_push_data(self.full.iloc[train]), self.set_push_data(self.full.iloc[test])]for train,test in self.splitter.split(self.full)]
       
    
    def preprocess_if_necessary(self):
        os.makedirs(self.di,exist_ok=True)
        if not os.path.exists(self.preprocessed_di):
            self.fea=Feature_Crawler(self.start,self.last,self.order_list,self.order_name,self.movie_only)
            #TSV データを使う用(時間がかかる)
            if self.tsv:
                self.tsv=Tsv_Crawler()
                self.full=self.tsv.title.join(self.fea.feature,how="inner")
            else:
                self.full=self.fea.feature

            if self.optional_data is not None:
                self.full = self.full.join(self.optional_data,how="inner")
            self.elminate_not_have_nessesary()
            self.preprocess()
            self.full.to_csv(self.preprocessed_di)
        self.full=pd.read_csv(self.preprocessed_di,index_col=0)
        #self.full=self.full.drop('Unnamed: 0',axis=1) 
    
    @property
    def preprocessed_di(self):
        if self.order_name is None:
            return self.di+"/"+"_s"+str(self.start)+"_l"+str(self.last)+".csv"
        #"_".join(self.feature_list)+
        else:
            return self.di+"/"+self.order_name+".csv"
        
    def pca(self,buf,name,dim):
        index=buf.index

        pca=PCA()
        buf.apply(lambda x: (x-x.mean())/x.std(), axis=0)
        pca.fit(buf)
        buf=pd.DataFrame(pca.transform(buf))
        buf=buf.iloc[:,:dim]
        buf.index=index
        buf.columns=buf.columns = ['{}_{}'.format(name, i)  for i in range(len(buf.columns))]
        return buf
    
    def combine(self,buf,name):
        combine=[]
        for c in buf.columns:
            print(buf[c].sum(), len(buf)*self.combine_rate)
            if buf[c].sum()<len(buf)*self.combine_rate:
                combine.append(buf[c])
                buf=buf.drop(columns=c)
        combine=np.amax(pd.concat(combine,axis=1),axis=1)
        combine.name=name+"_ow"
        print(combine.name)
        return pd.concat([buf,combine],axis=1)
                
    
    def preprocess(self):
        
        for d in self.delete_col:
            try:
                self.full = self.full.drop(columns=d)
            except Exception as e:
                print(e,"self.full don't have "+d)
        
                
        for p in self.first_number_col:
            try:
                nums = self.full[p].str.split(',', expand =True)
                if len(nums.columns)>1:
                    nums.columns = ['{}_{}'.format(p, i)  for i in nums.columns]
                else:
                    nums.columns=[p]
                self.full = self.full.drop(p,axis=1)
                
                split=2 #2つまで
                for i,n in enumerate(nums.columns):
                    if i>=split:
                        break
                    nums[n]=nums[n].astype(str).str.extract(r'(\d+)').astype(float)
                    nums[n].name=nums.columns[i]
                    self.full=pd.concat((self.full,nums[n]),axis=1)
                #self.full[p]=nums.astype(str).str.extract(r'(\d+)').astype(float)
            except Exception as e:
                print(e,"self.full don't have "+p)
        
                
        
        for g in self.genre:
            try:
                mlb = MultiLabelBinarizer()
                self.full[g]=self.full[g].map(lambda x: x.split(",")) 
                genres = pd.DataFrame(mlb.fit_transform(self.full[g]),columns=mlb.classes_)
                """
                try:
                    genres = genres.drop('\\N',axis=1)
                except Exception as e:
                    print(e,"genres don't have \\N")
                """
                genres.index = self.full.index
                #name
                genres.columns = ['{}_{}'.format(g, i)  for i in genres.columns]
                genres=self.combine(genres,g)
                self.full = self.full.drop(g,axis=1)
                self.full=pd.concat((self.full,genres),axis=1)
            except Exception as e:
                print(e,"self.full don't have "+g)
        
        for k in self.categorical_col:
            try:
                series = self.full[k]
                buf = pd.get_dummies(series)
                buf.loc[series.isna()] = None
                #name
                buf.columns = ['{}_{}'.format(k, i)  for i in buf.columns]
                buf=self.combine(buf,k)
                self.full = self.full.drop(k, axis=1)
                self.full = pd.concat([self.full, buf], axis=1)
            except Exception as e:
                 print(e,"self.full don't have "+k)
               
        self.full = self.full.replace('\\N',np.nan)
        
        for l in self.log:
            try:
                self.full[l] = self.full[l].apply(log)
            except Exception as e:
                print(e,"self.full don't have "+l)
                
        
        for d in self.date:
            try:
                date = self.full[d].str.split('-', expand =True).astype(float)
                date.columns=['year','month','day']
                date = date.drop('year',axis=1)
                self.full = self.full.drop(d,axis=1)
                self.full=pd.concat((self.full,date),axis=1)
            except Exception as e:
                print(e,"self.full don't have "+d)
        
        if self.doc_embed_dim:
            model = Doc2Vec.load('enwiki_dbow/doc2vec.bin')
            for w in self.word:
                if w=='keywords':
                    split_words=ft.partial(re.split,',''|'' ')
                elif w=='story_line':
                    split_words=ft.partial(re.split,' ''|''\n')
                elif w=='title':
                    split_words=lambda x:[x]
                
                buf=self.full[w].map(split_words).map(model.infer_vector).apply(pd.Series)
                buf=self.pca(buf,w,self.doc_embed_dim)
                
                #self.full = self.full.drop(w,axis=1)
                self.full=pd.concat((self.full,buf),axis=1)
                
        if self.image_embed_dim:
            print(self.full.reset_index())
            if self.tsv:
                index_column="index"
            else:
                index_column='titleId'
            image=self.full.reset_index()[index_column]
            image.index=self.full.index
            image=image.apply(load_image).apply(lambda x: torch.unsqueeze(x,0)).apply(nn.Sequential(*list(models.resnet18(pretrained=True).children())[:-1])).apply(lambda x:torch.squeeze(x).detach().numpy()).apply(pd.Series)
            #.apply(self.transform)
            image=self.pca(image,"poster_image",self.image_embed_dim)
            self.full=pd.concat((self.full,image),axis=1)
        
    def elminate_not_have_nessesary(self):
        self.full=self.full.dropna(subset=self.not_none_col)
        if self.target_col is not None:
            self.full=self.full.dropna(subset=[self.target_col])
        
    def set_push_data(self,panda):
        class push_data():
            def __init__(self,panda=panda,target=self.target_col,word=True,words=self.word, eng_poster=False, w_poster=False):
                self.full=panda
                self.full
                self.tar=target
                if target is not None:
                    self.target=self.full[target]
                    self.explain=self.full.drop(columns=target)
                self.wor=word
                self.word_col=words
                self.word = self.explain[words]
                self.explain=self.explain.drop(words,axis=1)
                    
                self.eng_poster=eng_poster
                self.w_poster=w_poster
                self.full_title=list(self.full.index)
                self.image_loader=load_image
                self.j_image_loader=ft.partial(load_image, option="jap")


            def __len__(self):
                return len(self.full)
            
            def __add__(self,other):
                return push_data(pd.concat([self.full,other.full]),self.tar,self.wor,self.word_col,self.eng_poster,self.w_poster)
            
            def split(self,rate=0.1):
                return [push_data(self.full.iloc[num],self.tar,self.wor,self.word_col,self.eng_poster,self.w_poster) for num in train_test_split(range(len(self)), test_size=rate)]

            def __getitem__(self,idx):
                transform = transforms.Compose(
                    [
                        transforms.ToTensor(),
                        transforms.Lambda(one_to_three),
                        transforms.Resize([300,256]),
                        transforms.ToTensor()
                    ])
    
                poster=self.image_loader(self.full_title[idx])
                #他のデータも(ex　title,size)
                return poster, self.explain.iloc[idx].to_numpy().astype('float64'), self.target.iloc[idx]
                
                """
                if self.wor:
                    if self.tar is not None:
                        #英語ポスターと日本語ポスター
                        if self.w_poster:
                            print(self.full_title[idx])
                            poster=transform(self.image_loader(self.full_title[idx]))
                            j_poster=transform(self.j_image_loader(self.full_title[idx]))
                            #print(self.explain.iloc[idx])
                            return (poster,j_poster) ,self.word.iloc[idx].values.tolist(), self.explain.iloc[idx].to_numpy().astype('float64'),self.target.iloc[idx]


                        #英ポスター
                        if self.eng_poster:
                            poster=transform(self.image_loader(self.full_title[idx]))
                            #他のデータも(ex　title,size)
                            return poster,self.word.iloc[idx].values.tolist(), self.explain.iloc[idx].to_numpy().astype('float64'), self.target.iloc[idx]


                        return self.word.iloc[idx].values.tolist(), self.explain.iloc[idx].to_numpy().astype('float64'), self.target.iloc[idx]

                    else:
                        if self.w_poster:
                            print(self.full_title[idx])
                            poster=transform(self.image_loader(self.full_title[idx]))
                            j_poster=transform(self.j_image_loader(self.full_title[idx]))
                            #print(self.explain.iloc[idx])
                            return (poster,j_poster) ,self.word.iloc[idx].values.tolist(), self.explain.iloc[idx].to_numpy().astype('float64')


                        #英ポスター
                        if self.eng_poster:
                            poster=transform(self.image_loader(self.full_title[idx]))
                            #他のデータも(ex　title,size)
                            return poster,self.word.iloc[idx].values.tolist(), self.explain.iloc[idx].to_numpy().astype('float64')


                        return  self.word.iloc[idx].values.tolist(), self.explain.iloc[idx].to_numpy().astype('float64')
                else:
                    if self.tar is not None:
                        #英語ポスターと日本語ポスター
                        if self.w_poster:
                            print(self.full_title[idx])
                            poster=transform(self.image_loader(self.full_title[idx]))
                            j_poster=transform(self.j_image_loader(self.full_title[idx]))
                            #print(self.explain.iloc[idx])
                            return (poster,j_poster) , self.explain.iloc[idx].to_numpy().astype('float64'),self.target.iloc[idx]


                        #英ポスター
                        if self.eng_poster:
                            poster=transform(self.image_loader(self.full_title[idx]))
                            #他のデータも(ex　title,size)
                            return poster, self.explain.iloc[idx].to_numpy().astype('float64'), self.target.iloc[idx]


                        return self.word.iloc[idx].values.tolist(), self.explain.iloc[idx].to_numpy().astype('float64'), self.target.iloc[idx]

                    else:
                        if self.w_poster:
                            print(self.full_title[idx])
                            poster=transform(self.image_loader(self.full_title[idx]))
                            j_poster=transform(self.j_image_loader(self.full_title[idx]))
                            #print(self.explain.iloc[idx])
                            return (poster,j_poster) , self.explain.iloc[idx].to_numpy().astype('float64')


                        #英ポスター
                        if self.eng_poster:
                            poster=transform(self.image_loader(self.full_title[idx]))
                            #他のデータも(ex　title,size)
                            return poster, self.explain.iloc[idx].to_numpy().astype('float64')


                        return  self.word.iloc[idx].values.tolist(), self.explain.iloc[idx].to_numpy().astype('float64')
               
               """
                    
        return push_data
            



        