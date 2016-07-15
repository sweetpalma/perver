#!/usr/bin/python
# coding: utf-8
# Perver - tiny Python 3 server for perverts.
# Check README and LICENSE for details.
from sys import platform as os_platform
from hashlib import sha1 as hash
from urllib.parse import unquote
from traceback import format_exc
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
__version__ = '0.2'


# Checking versions:
# 'yield from' will raise error anyway.
if sys.version_info < (3, 4):
	raise 'Asyncio requires Python 3.4.'


# Handling HTTP requests:
class PerverHandler:

	# Path substitution pattern:
	path_pattern = re.compile(r'(\{.+?\})')
	
	
	# Making client ID using cut SHA hash:
	def get_id(self):
		clnt = self.client
		ident = (str(clnt.ip) + str(clnt.agent)).encode(self.server.encoding)
		hashed = hash(ident).digest()[:self.server.length_id]
		return base64.urlsafe_b64encode(hashed).decode(self.server.encoding)[:-2]

	
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
		filename, extension = os.path.splitext(path)
		if extension in self.server.route_type:
			return self.server.route_type[extension]
		elif extension == '':
			return 'text/html'
		else:
			return self.server.route_type['other']
		
		
	# Sending file:
	@asyncio.coroutine
	def respond_file(self, path):
		try:
			with open(path, "rb") as file:
				size = os.path.getsize(path)
				yield from self.respond(200, file.read(), type=self.form_type(path), length=size)
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
		script = asyncio.coroutine(script)
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
		self.form_header('Content-Type', type + ';charset=' + encoding)
		self.form_header('Accept-Charset', encoding)
		self.form_header('Server', 'Perver/' + __version__)
		
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
	
	
	# Parsing GET:
	def parse_get(self, path, separator='&'):
		get = path.split('?')
		if len(path) > 1 and len(get) == 2:
			unq = lambda x: map(unquote, x)
			vars = get[1].split(separator)
			get = dict(tuple([unq(arg.split('=')[:2]) for arg in vars]))
			return get
		else:
			return {}
		
		
	# Parsing client data:
	@asyncio.coroutine
	def parse(self, header, content=b''):
	
		# Connecting client:
		client = PerverClient()
		
		# Saving:
		client.byte_header = header
		client.byte_content = content
		
		# Decoding:
		header = header.decode(self.server.encoding)

		# Encoding arguments:
		args = [tuple(arg.split(': ')) for arg in header.split('\r\n')]
		
		# Invalid header:
		if len(args) < 3:
			self.respond_error(400)
			return
		
		# Request type, path and version:
		client.type, path, client.version = args[0][0].split(' ')
		client.path = unquote(path.split('?')[0])
		client.path_dir = '/'.join(client.path.split('/')[:-1])
		args = dict(args[1:-2])
		
		# Fixing path dir:
		if client.path_dir == '':
			client.path_dir = '/'
		
		# Small variables:
		client.agent = 'User-Agent' in args and args['User-Agent'] or 'Bot'
		client.mime = self.form_type(client.path)
		
		# Parsing GET:
		client.get = self.parse_get(path)
		
		# Parsing POST:
		post_args = content.decode(self.server.encoding).replace('+', ' ')
		client.post = self.parse_get(''.join(['?', post_args]))
		
		# Working with cookies:
		if 'Cookie' in args:
			cookie = args['Cookie'].replace('; ', ';')
			client.cookie = self.parse_get('?' + cookie, separator=';')
		
		# Arguments:
		client.time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
		client.ip = self.ip
		client.port = self.port
		
		# Making script client:
		self.client = client
		
		# Working with client ID:
		client.id = self.get_id()
		
		# Adding client to server database:
		if not client.id in self.server.client:
			self.server.client[client.id] = {}
			
		# Setting cookie:
		self.client.header['Set-Cookie'] = 'id=' + client.id
		# It could be overriden later.
			
		# Client containers:
		client.container = self.server.client[client.id]
		
		# Retrieving client:
		return self.client
	
	
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
		
		# Reading header:
		header, length = b'', 0
		while True:
			try:
				line = yield from reader.readline()
				if line == b'\r\n' or not line:
					break
				if line.startswith(b'Content-Length'):
					length = int(line.split(b':')[1])
				header = header + line
			except:
				break
			
		# Reading content:
		content = b''
		if length > 0:
			content = yield from reader.read(length)
		
		# Parsing data:
		client = yield from self.parse(header, content)
		
		# In case of disconnection:
		if not client:
			self.writer.close()
			return
		
		# Logging:
		log.info(' '.join([
			client.time, 
			client.type, 
			client.path, 
			client.ip
		]))
		
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
			
		# Global errors:
		except (KeyboardInterrupt, SystemExit) as exception:
			raise exception
				
		# Catching errors:
		except:
			log.warning('Exception caught!')
			log.error(format_exc())
			yield from self.respond_error(500)
			return
			
		
		
		
# Script client:
class PerverClient:
	
	# PARAMETERS:
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
		self.mime = 'application'
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
		
		
	# Making HTML template:
	def html(self, body, head='', doctype='html'):
		doctype = '<!DOCTYPE %s>' % doctype
		head = '\r\n'.join(['<head>', head, '</head>'])
		body = '\r\n'.join(['<body>', body, '</body>'])
		return '\r\n'.join([doctype, head, body])
		
		
	# Making forms:
	def form(self, action, method, *inputs, id=''):
		html = '<form action="%s" method="%s" id="%s">' % (action, method, id)
		inputs = [list(inp.items()) for inp in inputs]
		for input in inputs:
			args = ' '.join('%s="%s"' % arg for arg in input)
			html = '\r\n'.join([html, '<input %s><br>' % args])
		return ''.join([html, '</form>'])
		
	
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
	timeout  = 5
	
	# Client ID length:
	length_id = 10
	# I highly recommend not to change this value.
	
	# Routing paths:
	route_get  = {}
	route_post = {}
	route_static = {}
	
	# MIME types:
	route_type = {
		'.html': 'text/html',
		'.txt':  'text/plain',
		'.jpg':  'image/jpeg',
		'.png':  'image/png',
		'.css':  'text/css',
		'other': 'application'
	}
	
	# Active clients list:
	client = {}
	
	# METHODS:
	# Routing GET:
	# DECORATOR:
	def get(self, path):
		def callback(func):
			self.route_get[path] = func
			return func
		return callback
	
	
	# Routing POST:
	# DECORATOR:
	def post(self, path):
		def callback(func):
			self.route_post[path] = func
			return func
		return callback
	
	
	# Global routing:
	# DECORATOR:
	def route(self, path):
		def callback(func):
			self.route_post[path] = func
			self.route_get[path] = func
			return func
		return callback
		
		
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
		
			# Establishing logging:
			start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
			
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
			log.info('Perver has started at ' + start_time + '.')
			self._loop.run_forever()
				
		# Catched!
		except OSError:
			log.error('OS error, probably server is already running at that port.')
			os.system('pause')
	
	
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
			del handler
		except asyncio.TimeoutError:
			log.error('Timed out.')
		except KeyboardInterrupt:
			log.error('Interrupted by user.')
			self.stop()
		except SystemExit:
			self.stop()
		except:
			log.warning('Exception caught!')
			log.error(format_exc())
			return
