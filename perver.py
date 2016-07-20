#!/usr/bin/python
# coding: utf-8
# Perver - tiny Python 3 server for perverts.
# Check README and LICENSE for details.
from sys import platform as os_platform
from hashlib import sha1 as hash_id
from urllib.parse import unquote
from mimetypes import guess_type
from traceback import format_exc
from functools import wraps
import concurrent.futures
import logging as log
import asyncio
import base64
import time
import sys
import os
import re


# Version control:
__author__ = 'SweetPalma'
__version__ = '0.25'


# Handling HTTP requests:
class PerverHandler:

	# Path substitution pattern:
	path_pattern = re.compile(r'(\{.+?\})')
	
	# Making client ID using cut SHA hash:
	def get_id(self, clnt):
		ident = (str(clnt.ip) + str(clnt.agent)).encode(self.server.encoding)
		hashed = hash_id(ident).digest()[:self.server.length_id]
		cook = base64.urlsafe_b64encode(hashed).decode(self.server.encoding)
		return cook[:-2]

	# Power of regexp!
	def check_route(self, path, map):
		
		# Pure path:
		if path in map:
			return (map[path], {})
			
		# Path with substitutions:
		right_path, groups = False, sys.maxsize
		for route in map:
		
			# Removing retarded slash in the end of path:
			path = path.endswith('/') and path[:-1] or path
		
			# Patterns:
			path_pattern = '^' + self.path_pattern.sub('([^/]+)', route) + '$'
			matched = re.match(path_pattern, path)
			
			# Testing:
			if matched:
				keys = [key[1:-1] for key in self.path_pattern.findall(route)]
				values = list(matched.groups())
				if len(values) < groups:
					groups = len(values)
					right_path = (map[route], dict(zip(keys, values)))

		# In case of fail:
		return right_path

	# Appending certain header lines:
	def form_header(self, arg, var):
		self.header = self.header + arg + ': ' + var + '\r\n'
		
	# Retrieving type:
	def form_type(self, path):
		type = guess_type(path)[0]
		if type:
			return type
		else:
			return 'text/html'
		
	# Sending file:
	@asyncio.coroutine
	def respond_file(self, path):
		try:
			with open(path, "rb") as file:
				size = os.path.getsize(path)
				yield from self.respond(
					200, 
					file.read(), 
					type=self.form_type(path), 
					length=size
				)
		except IOError:
			yield from self.respond_error(404)
				
	# Forming error:
	@asyncio.coroutine
	def respond_error(self, number, custom=None):
		error = {
			400: 'Bad Request',
			404: 'Not Found',
			500: 'Internal Error',
		}
		error_text = number in error and error[number] or 'Unknown Error'
		yield from self.respond(number, str(number) + ' ' + error_text)
		
	# Executing client script:
	@asyncio.coroutine
	def respond_script(self, script, keys={}):
		script_result = yield from script(self.client, **keys)
		if not script_result:
			script_result = b''
		yield from self.respond(
			self.client.status, 
			script_result,
			header=self.client.header, 
			type=self.client.mime
		)
	
	# Pure data response:
	@asyncio.coroutine
	def respond(self, status, content=b'', type='text/html', length=None, header={}):
		
		# Forming header:
		encoding = self.server.encoding
		self.header = 'HTTP/1.1 ' + str(status) + '\r\n'
		self.form_header('Accept-Charset', encoding)
		self.form_header('Server', 'Perver/' + __version__)
		
		# Setting mime type and encoding:
		if type.split('/')[0] == 'text':
			ctype = type + ';charset=' + encoding
		else:
			ctype = type
		self.form_header('Content-Type', ctype)
		
		# Working with custom headers:
		for key, value in header.items():
			self.form_header(key, value)
			
		# Encoding content:
		if not isinstance(content, bytes):
			content = content.encode(encoding)
			
		# Forming content length:
		length = length or len(content)
		self.form_header('Content-Length', str(length))
		
		# Forming response:
		header = self.header.encode(encoding)
		response = header + b'\r\n' + content + b'\r\n'
		
		# Go:
		self.writer.write(response)
		self.writer.write_eof()
	
	# Parsing GET and COOKIES:
	@asyncio.coroutine
	def parse(self, path):
	
		# Preparing %key%=%value% regex:
		get_word = '[^=;&?]'
		pattern = '(%s+)=(%s+)' % (get_word, get_word)

		# Unquoting map:
		unq = lambda x: map(unquote, x)
		
		# Replacing retarded pluses to spaces in path:
		path = path.replace('+', ' ')
		
		# Working:
		matched = [unq(x) for x in re.findall(pattern, path)]
		return dict(matched)
			
	# Parsing POST:
	@asyncio.coroutine
	def parse_post(self, content, type, boundary):
	
		# Establishing default encoding:
		encoding = self.server.encoding

		# Parsing multipart:
		if type == 'multipart/form-data':
			fields = content.split(boundary)
			fields_dict = {}
			for field in fields:
				field_rows = field.split(b'\r\n\r\n')
				if len(field_rows) == 2:
				
					# Basic header and value:
					header, value = field_rows
					value = value[:-2]
					
					# Decoding key:
					key = re.findall(b';[ ]*name="([^;]+)"', header)[0]
					key = key.decode(encoding)
					
					# Checking content-type:
					ctype = re.search(b'Content-Type: ([^;]+)$', header)
					
					# File upload:
					if ctype:
						if value == b'' or value == b'\r\n':
							continue
						ctype = ctype.group()
						fname = re.findall(b';[ ]*filename="([^;]+)"', header)
						fname = len(fname) == 1 and fname[0] or b'unknown'
						fields_dict[key] = {
							'filename': fname.decode(encoding),
							'mime': ctype.decode(encoding),
							'file': value,
						}
						
					# Basic field:
					else:
						fields_dict[key] = value.decode(encoding)
						
			return fields_dict
		
		# Parsing average urlencoded:
		else:
			if isinstance(content, bytes):
				content = content.decode(encoding)
			return self.parse(content)
		
		
	# Parsing client data:
	@asyncio.coroutine
	def build_client(self, header_raw, content_raw=b''):
	
		# Checking value in dict:
		def safe_dict(dictionary, value, default):
			if value in dictionary:
				return dictionary[value]
			else:
				return default
				
		# Decoding:
		try:
		
			# Decoding header:
			header_decoded = header_raw.decode(self.server.encoding)
		
			# Three basic values: request type, path and version:
			pattern = '^(GET|POST) ([A-Za-z0-9_.-~?&%]+) (HTTP/1.1|HTTP/1.0)'
			type, path, version = re.findall(pattern, header_decoded)[0]
			
			# Splitting GET and PATH:
			if '?' in path:
				path, GET = path.split('?')
			else:
				GET = ''
		
			# Raw header to header dictionary:
			pattern = '([^:]+):[ ]*(.+)\r\n'
			header = dict(re.findall(pattern, header_decoded))
			
			# Basic client variables:
			client = PerverClient()
			client.version = version
			client.type, client.path = type, unquote(path)
			client.path_dir = '/'.join(unquote(path).split('/')[:-1])
			
			# Client header:
			client.header_raw, client.content_raw = header_raw, content_raw
			client.content_type = safe_dict(header, 'Content-Type', '')
			client.content_length = safe_dict(header, 'Content-Length', 0)
			client.agent = safe_dict(header, 'User-Agent', 'Unknown')
			client.mime = self.form_type(client.path)
			client.form_type = client.content_type.split(';')[0]
			
			# Server client values:
			client.ip, client.port, client.time = self.ip, self.port, self.time
			client.id = self.get_id(client)
			
			# POST boundary:
			boundary = re.findall('boundary=(-*[0-9]*)', client.content_type)
			if len(boundary) > 0:
				boundary = boundary[0].encode(self.server.encoding)
			else:
				boundary = b''
			
			# POST/GET/COOKIES:
			client.get =     yield from self.parse(GET)
			client.post =    yield from self.parse_post(content_raw, client.form_type, boundary)
			client.cookies = yield from self.parse(safe_dict(header, 'Cookie', ''))
			
			# Client ID cookie, can be overrided later:
			client.header['Set-Cookie'] = 'id=' + client.id
			
			# Client server-side container:
			if not client.id in self.server.client:
				self.server.client[client.id] = {}
			client.container = self.server.client[client.id]
			
			# Fixing client path dir:
			if client.path_dir == '':
				client.path_dir = '/'
			
			# Done!
			return client
			
		# In case of fail:
		except BaseException as exc:
			log.warning('Error parsing user request.')
			yield from self.respond_error(400) 
			raise exc
			
	# Handling requests:
	@asyncio.coroutine
	def handle_request(self, server, reader, writer):
		
		# Constructing:
		self.server = server
		
		# Preparing basic values:
		peername = writer.get_extra_info('peername')
		ip, port = peername[0], peername[1]
		
		# Client basic values:
		self.ip = ip
		self.port = port
		self.reader = reader
		self.writer = writer
		self.time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
		
		# Client info, used in logging:
		client_info = ' '.join([
			self.time,
			self.ip,
		])
		
		# Reading header:
		error = ''
		header, length = b'', 0
		while True:
			try:
			
				# Reading:
				line = yield from reader.readline()
				
				# Setting request type and maximal request size:
				if header == b'':
					if line.startswith(b'POST'):
						request_type = b'POST'
						request_max = self.server.post_max	
					else:
						request_type = b'GET'
						request_max = self.server.get_max
				
				# Setting break:
				if line == b'\r\n' or not line:
					break
					
				# Reading content length:
				if line.startswith(b'Content-Length'):
					length = int(line.split(b':')[1])
					
				# Reading header:
				header = header + line
				
			except:
				break
		
		# Reading content:
		content = b''
		if length > 0 and length < request_max:
			content = yield from reader.readexactly(length)
			
		# Close connection in case of big file:
		elif length > request_max:
			log.info(client_info + ' REQUEST IS TOO BIG')
			self.writer.close()
			return
		
		# Parsing data:
		self.client = yield from self.build_client(header, content)
		client = self.client
		
		# In case of disconnection:
		if not client:
			log.info(client_info + ' CLOSED CONNECTION')
			self.writer.close()
			return
			
		# Logging full information:
		else:
			client_info = client_info + ' ' + ' '.join([
				client.type,
				client.path,
			])
			log.info(client_info)
		
		# Finding correct response:
		try:
		
			# Checking routing:
			route_post = self.check_route(client.path, self.server.route_post)
			route_get = self.check_route(client.path, self.server.route_get)
			if client.type == 'POST' and route_post:
				yield from self.respond_script(*route_post)
				return
			if client.type == 'GET' and route_get:
				yield from self.respond_script(*route_get)
				return
				
			# Checking static files:
			for dir, real in self.server.route_static.items():
				if client.path.startswith(dir):
					filepath = client.path.replace(dir, real, 1)
					yield from self.respond_file(filepath[1:])
					return
			
			# Routing 404 error:
			yield from self.respond_error(404)
			return
			
		# Timeout/Cancelled:
		except concurrent.futures._base.CancelledError:
			log.warning('Task was cancelled.')
			yield from self.respond_error(500)
			pass
			
# Script client:
class PerverClient:
	
	# GET/POST arguments:
	get  = {}
	post = {}
	
	# Client headers:
	status = 200
	header = {}
	cookie = {}
	mime = 'text/html'
	
	# Redirection:
	def redirect(self, page):
		self.header['Location'] = page
		self.status = 302
		return 'Redirecting...'
	
	# Templating:
	def template(self, text, **replace):
		for key, value in replace.items():
			text = text.replace('{' + key + '}', value)
		return text
		
	# Rendering page:
	def render(self, filename, **replace):
		file = open(filename, 'r')
		return self.template(file.read(), **replace)
	
	# Retrieving file:
	def file(self, filename):
		self.mime = guess_type(filename)[0]
		file = open(filename, 'rb')
		return file.read()
	
	# Own header:
	def set_header(self, key, value):
		self.header[key] = value
	
	# Cookies:
	def set_cookie(self, name, value):
		self.header['Set-Cookie'] = name + '=' + value +';'
		
	# Status:
	def set_status(self, status):
		self.status = status
		
	# Mime:
	def set_mime(self, mime):
		self.mime = mime
		
	# Making HTML template:
	def html(self, body, head='', doctype='html'):
		doctype = '<!DOCTYPE %s>' % doctype
		head = '\r\n'.join(['<head>', head, '</head>'])
		body = '\r\n'.join(['<body>', body, '</body>'])
		return '\r\n'.join([doctype, head, body])
		
	# Making forms:
	def form(self, action, method, *inputs, id='', multipart=False):
		
		# Loading files or average form:
		if multipart:
			enctype='multipart/form-data'
		else:
			enctype='application/x-www-form-urlencoded'
	
		# Making form:
		form_desc = (action, method, id, enctype)
		html = '<form action="%s" method="%s" id="%s" enctype="%s">' % form_desc
		inputs = [list(inp.items()) for inp in inputs]
		for input in inputs:
			args = ' '.join('%s="%s"' % arg for arg in input)
			html = '\r\n'.join([html, '<input %s><br>' % args])
		return ''.join([html, '</form>'])
		
	# Multipart form:
	def form_multipart(self, *args, **kargs):
		kargs['multipart'] = True
		return self.form(*args, **kargs)
		
	# Part of the previous function:
	def input(self, name, **args):
		return dict({'name':name}, **args)
	
	# Input submit:
	def input_submit(self, value='Submit', **args):	
		return {'type':'submit', 'value':value}

		
# Perver Server itself:
class Perver:

	# PARAMETERS:
	# Main server values:
	encoding = 'utf-8'
	backlog  = 5
	timeout  = 30
	
	# Maximal requests length:
	get_max  = 1024 * 8
	post_max = 1024 * 1024 * 100
	
	# Client ID length:
	length_id = 10
	# I highly recommend not to change this value.
	
	# Routing paths:
	route_get  = {}
	route_post = {}
	route_static = {}
	
	# Active clients list:
	client = {}
	
	# METHODS:
	# Routing GET:
	# DECORATOR:
	def get(self, path):
		def decorator(func):
			@wraps(func)
			def wrapper(*args, **kwds):
				return asyncio.coroutine(func)(*args, **kwds)
			self.route_get[path] = wrapper
			return wrapper
		return decorator
	
	# Routing POST:
	# DECORATOR:
	def post(self, path):
		def decorator(func):
			@wraps(func)
			def wrapper(*args, **kwds):
				return asyncio.coroutine(func)(*args, **kwds)
			self.route_post[path] = wrapper
			return wrapper
		return decorator
	
	# Global routing:
	# DECORATOR:
	def route(self, path):
		def decorator(func):
			@wraps(func)
			def wrapper(*args, **kwds):
				return asyncio.coroutine(func)(*args, **kwds)
			self.route_post[path] = wrapper
			self.route_get[path] = wrapper
			return wrapper
		return decorator
		
	# Adding static route:
	def static(self, web, local):
		local = local.replace('\\', '/')
		if not (local.startswith('/') and os.path.isabs(local)):
			local = '/' + local
		if not local.endswith('/'):
			local = local + '/'
		self.route_static[web] = local
	
	# Starting:
	def start(self, host='', port=80):
	
		# Configuring:
		self.host, self.port = host, port
		log.basicConfig(level=log.INFO, format='%(levelname)s: %(message)s')
		
		# Nice header:
		if os_platform == 'win32':
			os.system('title Perver v' + __version__)
		
		# Catching socket errors:
		try:
		
			# Starting server:
			self._loop = asyncio.get_event_loop() 
			self._server = asyncio.start_server(
				self.handler, 
				host=host, 
				port=port, 
				backlog=self.backlog,
				reuse_address=True,
			)
			self._server = self._loop.run_until_complete(self._server)
			start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
			log.info('Perver has started at ' + start_time + '.')
			self._loop.run_forever()
				
		# Catched!
		except OSError:
			log.error('OS error, probably server is already running at that port.')
	
	# Stop?
	def stop(self):
		self._server.close()
		self._loop.stop()
			
	# Main handler:
	@asyncio.coroutine
	def handler(self, reader, writer):
		try:
			handler = PerverHandler()
			yield from asyncio.wait_for(handler.handle_request(self, reader, writer), timeout=self.timeout)
		except (asyncio.TimeoutError):
			log.warning('Timed out.')
		except KeyboardInterrupt:
			log.warning('Interrupted by user.')
			self.stop()
		except SystemExit:
			self.stop()
		except:
			log.warning('Exception caught! \r\n' + format_exc())
			
# Not standalone:
if __name__ == '__main__':
	print('Perver is not a standalone application. Use it as framework.')
	print('Check "github.com/SweetPalma/Perver" for details.')