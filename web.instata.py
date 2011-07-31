""" 
 Takes CSV as input and generates a HTML document with the data items marked up with Schema.org terms.

@author: Michael Hausenblas, http://sw-app.org/mic.xhtml#i
@since: 2011-07-30
@status: init
"""

import os
import sys
sys.path.insert(0, os.getcwd() + '/lib')
sys.path.insert(0, os.getcwd() + '/lib/rdflib')
sys.path.insert(0, os.getcwd() + '/lib/rdfextras')
import getopt
import StringIO
import shutil
import datetime
import rdflib
import rdfextras
from rdflib import *
from rdflib.plugin import PluginException
import rdflib_schemaorg_csv
from bottle import SimpleTemplate

rdflib.plugin.register('sparql', rdflib.query.Processor, 'rdfextras.sparql.processor', 'Processor')
rdflib.plugin.register('sparql', rdflib.query.Result, 'sparql.query', 'SPARQLQueryResult')

class InstantWebDataPublisher(object):
	
	DEBUG = True
	
	# some config stuff we gonna need:
	TEMPLATES_DIR = 'templates/'
	OUTPUT_DIR = 'output/'
	BASE_TEMPLATE = TEMPLATES_DIR + 'base.tpl'
	BASE_STYLE_FILE = 'web.instata-style.css'
	
	# internal stuff
	NAMESPACES = {	'schema' : Namespace('http://schema.org/'), 
					'scsv' : Namespace('http://purl.org/NET/schema-org-csv#'), 
					'dc' : Namespace('http://purl.org/dc/terms/') 
	}
	
	# content creation queries:
	BASE_QUERY = """SELECT ?row ?rowType ?cell ?colTitle ?cellType ?val WHERE { 
					?table a scsv:Table ;
						   scsv:row ?row .
					?row a ?rowType ; 
						scsv:cell ?cell .
					OPTIONAL {	?cell a ?cellType ;
					 				rdf:value ?val . }
					OPTIONAL {	?cell dc:title ?colTitle . }
	}"""
	
	def __init__(self):
		self.g = None
		self.doc_url = ""
		self.base_uri = ""
		if not os.path.exists(InstantWebDataPublisher.OUTPUT_DIR): # make sure output dir exists
			os.makedirs(InstantWebDataPublisher.OUTPUT_DIR)

	def parse(self, doc_url, base_uri):
		self.doc_url = doc_url
		self.base_uri = base_uri
		self.g = ConjunctiveGraph("IOMemory")
		self.g.parse(location=doc_url, format="schemaorg_csv", csv_file_URI=base_uri)
	
	def render(self):
		tpl = SimpleTemplate(name=InstantWebDataPublisher.BASE_TEMPLATE)
		wi_last_update = datetime.datetime.utcnow().replace(microsecond = 0)
		if InstantWebDataPublisher.DEBUG: print('[web.instata:DEBUG] querying input data ...')
		res = self.g.query(InstantWebDataPublisher.BASE_QUERY, initNs=InstantWebDataPublisher.NAMESPACES)
		if InstantWebDataPublisher.DEBUG: print('[web.instata:DEBUG] got %s rows' %(len(res)))
		
		self.table_header = []
		self.table_rows = []
		# ?row ?rowType ?cell ?colTitle ?cellType ?val
		for r in res:
			if InstantWebDataPublisher.DEBUG: print('[web.instata:DEBUG]  row: %s' %(r))
			if str(r[1]) == 'http://purl.org/NET/schema-org-csv#HeaderRow':
				# 0: rdflib.term.URIRef('http://example.org/instata/potd_0#row:1')
				# 1: rdflib.term.URIRef('http://purl.org/NET/schema-org-csv#HeaderRow')
				# 2: rdflib.term.URIRef('http://example.org/instata/potd_0#row:1,col:2')
				# 3: rdflib.term.Literal(u'name')
				# 4: None
				# 5: None
				self.table_header.append(r[3]) # ?colTitle
				if InstantWebDataPublisher.DEBUG: print('[web.instata:DEBUG]  header cell: %s' %(r[3]))
			else:
				# 0: rdflib.term.URIRef('http://example.org/instata/potd_0#row:2')
				# 1: rdflib.term.URIRef('http://purl.org/NET/schema-org-csv#Row')
				# 2: rdflib.term.URIRef('http://example.org/instata/potd_0#row:2,col:2')
				# 3: None
				# 4: rdflib.term.URIRef('http://schema.org/name')
				# 5: rdflib.term.Literal(u"Mom's World Famous Banana Bread")
				self.table_rows.append(r[5]) # ?val
				if InstantWebDataPublisher.DEBUG: print('[web.instata:DEBUG]  cell: %s' %(r[5]))
			
		# variables starting with ds_ refer to data space stuff, otherwise starting with wi_ signalling internal stuff:
		return tpl.render(ds_name=self.doc_url.split('/')[-1].split('.')[0],
						theader=self.table_header, 
						trows=self.table_rows, 
						wi_last_update=str(wi_last_update) + ' (UTC)')

	def instata(self, doc_url, base_uri):
		# get the data and render it
		self.parse(doc_url, base_uri)
		render_result = self.render()
		
		# output the result and copy style file
		result_file_name = InstantWebDataPublisher.OUTPUT_DIR + doc_url.split('/')[-1].split('.')[0] + ".html"
		result_file = open(result_file_name, 'w')
		result_file.write(render_result)
		result_file.close()
		shutil.copy2(InstantWebDataPublisher.TEMPLATES_DIR + InstantWebDataPublisher.BASE_STYLE_FILE, InstantWebDataPublisher.OUTPUT_DIR + InstantWebDataPublisher.BASE_STYLE_FILE)
		return result_file_name
	
	def dump_data(self, format='turtle'):
		if self.g:
			self.g.bind('schema', InstantWebDataPublisher.NAMESPACES['schema'], True)
			self.g.bind('scsv', InstantWebDataPublisher.NAMESPACES['scsv'], True)
			self.g.bind('dc', InstantWebDataPublisher.NAMESPACES['dc'], True)
			return self.g.serialize(format=format)
		else:
			return None

def usage():
	print("Usage: python web.instata.py -p {path to CSV file} {base URI for publishing}")
	print("Example: python web.instata.py -p test/potd_0.csv http://example.org/instata/potd_0")

if __name__ == "__main__":
	iwdp = InstantWebDataPublisher()
	
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hpd", ["help", "publish", "dump"])
		for opt, arg in opts:
			if opt in ("-h", "--help"):
				usage()
				sys.exit()
			elif opt in ("-p", "--publish"):
				(doc_url, base_uri) = (args[0], args[1])
				print("[web.instata] processing [%s] with base URI [%s] " %(doc_url, base_uri))
				r = iwdp.instata(doc_url, base_uri)
				print("[web.instata] result is now available at [%s]" %(r))
			elif opt in ("-d", "--dump"):
				(doc_url, base_uri) = (args[0], args[1])
				print("processing [%s] with base URI [%s] " %(doc_url, base_uri))
				iwdp.parse(doc_url, base_uri)
				print(iwdp.dump_data())
	except getopt.GetoptError, err:
		print str(err)
		usage()
		sys.exit(2)