.. image:: https://raw.githubusercontent.com/SweetPalma/Perver/master/logo.png
  :target: https://github.com/SweetPalma/Perver
  :alt: Perver Logo
  :align: right
Perver - small async Python http-server with embedded framework, based on asyncio and some magic.

    Copyright 2016 SweetPalma <sweet.palma@yandex.ru>

Perver is open sourced. See the `LICENSE <https://raw.githubusercontent.com/SweetPalma/Perver/master/LICENSE>`_ file for more information.

=============
perver.Perver
=============
Core of all other perversions, that's what you need to run own server.

encoding
--------
Server encoding. Default is 'utf-8'.

timeout
-------
Client request timeout. Default is 5 seconds.

get_max
-------
Maximal size of client GET request. Default is set to 8192 bytes.

post_max
--------
Maximal size of client POST request. Default is set to 1024 * 1024 * 100 = 100 Mbytes.

__init__(self)
--------------
Makes new Perver instance. Doesn't take any parameters.

start(self, host='', port=80)
-----------------------------
Starts the (mostly) infinite loop of server. Host is address which server will be responsible for, port is socket which server will listen to.

stop(self)
----------
Stops the Perver. Doesn't take any parameters.

static(self, web, local)
------------------------
Used for binding certain WEB path file request to certain LOCAL file directory. For example, if you will set WEB and LOCAL to '/', request like 'yoursite/test.png' will seek for 'test.png' in your server directory.

get(self, path)
---------------
DECORATOR: Binds all GET requests from path to certain function. Check `Routing <https://github.com/SweetPalma/Perver/blob/master/REFERENCE.rst#routing>`_ for more information.

post(self, path)
----------------
DECORATOR: Binds all POST requests from path to certain function. Check `Routing <https://github.com/SweetPalma/Perver/blob/master/REFERENCE.rst#routing>`_ for more information.

route(self, path)
-----------------
DECORATOR: Binds all POST/GET requests from path to certain function. Check `Routing <https://github.com/SweetPalma/Perver/blob/master/REFERENCE.rst#routing>`_ for more information.

Example:
--------
.. code-block:: python

  # Connecting Perver:
  from perver import Perver
  
  # Making new instance:
  server = Perver()

  # Routing all POST/GET requests to certain function:
  @server.route('/')
  def page_main(self):
      return 'Hello, Perverts!'
  
  # Starting server:
  server.start()
  
===================
perver.PerverClient
===================
That's what I named as 'self' in routing functions - that's all what you need to handle client data.

id
--
Client unique ID.

type
----
Request type - POST/GET.

ip
--
Client address.

port
----
Client connection port.

path
----
Client request path, already unquoted.

path_dir
--------
Client request path, with directory extracted.

agent
-----
Client User-Agent.

get
---
Dictionary with client GET arguments.

post
----
Dictionary with client POST arguments.

cookie
------
Dictionary with client cookies.

time
----
Client connection time.

container
---------
Dictionary with client server-side variables - you can use them to store session data.

redirect(self, page)
--------------------
Redirects client to a certain PAGE, using 302 status code.

template(self, text, **replace)
-------------------------------
Used in templating - returns TEXT with any {occurence} will be REPLACEd. For example, if you have text 'Hello, {name}!' and REPLACE is {'name':'world'} - you will get the text 'Hello, world!'.

render(self, filename, **replace)
---------------------------------
Same as template, but used in files. Returns file with FILENAME with any {occurence} REPLACEd.

file(self, filename)
--------------------
Returns file with FILENAME, binary.

set_header(self, key, value)
----------------------------
Sets custom client HTTP header.

set_cookie(self, key, value)
----------------------------
Sets custom client cookie, overriding default Perver ID Cookie.

set_status(self, status)
------------------------
Sets custom response status, overriding default 200.

set_mime(self, mime)
------------------------
Sets custom mime response.

html(self, body, head='', doctype='html')
-----------------------------------------
HTML-correct template for nice pages.

form(self, action, method, *inputs, id='', multipart=False)
-----------------------------------------------------------
Used for building forms. Check `Forms <https://github.com/SweetPalma/Perver/blob/master/REFERENCE.rst#forms>`_ for more information.

form_multipart(self, *args, **kargs)
------------------------------------
Works same as PerverClient.form, but with multipart argument set to True.

input(self, name, **args)
-------------------------
Single form input. Check `Forms <https://github.com/SweetPalma/Perver/blob/master/REFERENCE.rst#forms>`_ for more information.

input_submit(self, value='Submit', **args)
------------------------------------------
Form submit button. Check `Forms <https://github.com/SweetPalma/Perver/blob/master/REFERENCE.rst#forms>`_ for more information.

Example
-------
.. code-block:: python

  # Connecting Perver:
  from perver import Perver
  
  # Making new instance:
  server = Perver()

  # Redirecting to GET userinfo page:
  @server.route('/')
  def page_main(self):
      return self.redirect('/get?get=test')
	
  # Userinfo page:
  @server.route('/get')
  def page_main(self):
      user_info = '<br>'.join([
          'ID:', self.id,
          'IP:', self.ip,
          'UA:', self.agent,
          'GET:', str(self.get),
          'Coookie:', str(self.cookie)
	])
      return user_info
  
  # Starting server:
  server.start()
  
====================
perver.PerverHandler
====================
You don't really need to use this one. That's internal class that is used only for handling low-level HTTP data.
  
=======
Routing
=======
It's easy to describe this, using only one example:

Example
-------
.. code-block:: python

  # Connecting Perver:
  from perver import Perver
  
  # Making new instance:
  server = Perver()

  # Every root request will go here.
  @server.route('/')
  def page_main(self):
      return 'Hello, Anon!'
	
  # Requests like '/goofried', '/hello_world', '/_' will go here:
  @server.route('/{name}')
  def page_main(self, name):
      return self.template('Hello, {name}!', name=name)

  # Requests like '/Sweet/Palma', '/_/_' will go here:
  @server.route('/{name}/{surname}')
  def page_main(self, name, surname):
      return self.template('Hello, {name} {surname}!', name=name, surname=surname)
	
  # Requests like '/bye/world', '/sell/world' will go here:
  @server.route('/{what}/world')
  def page_main(self, what):
      return self.template('{what}, World!', what=what)
	
  # Starting server:
  server.start()
  
  
=====
Forms
=====
Python-ish way to build forms. `Read more about HTML forms here <http://www.w3schools.com/html/html_forms.asp>`_. By using form_input you just build HTML form using Python dictionary, all input tags are `still as in HTML <http://www.w3schools.com/tags/tag_input.asp>`_. Take a look at example:

Example #1
----------
Processing POST data:

.. code-block:: python

  # Connecting Perver:
  from perver import Perver
  
  # Making new instance:
  server = Perver()

  # Displaying form:
  @server.get('/')
  def show_form(self):
      return self.html(
          self.form('/', 'post',
              self.input('login', placeholder='Login'),
              self.input('password', type='password'),
              self.input_submit()
          ))
	
  # Displaying user-data:
  @server.post('/')
  def show_data(self):
      return self.html(
          '<br>'.join([
              '<b>Login:</b>', self.post['login'],
              '<b>Password:</b>', self.post['password']
          ]))
	
  # Starting server:
  server.start()
  
Example #2
----------
Uploading file to server directory.
WARNING: Perver is not intended to work with big files. That's a small framework for small projects that work with small files. Avoid using it for uploading files bigger than 100Mb.

.. code-block:: python

  # Connecting Perver:
  from perver import Perver

  # Making new instance:
  server = Perver()

  # Displaying form:
  @server.get('/')
  def test(self):
      status = 'status' in self.get and self.get['status'] or ''
      return self.html(
          status + ' ' + self.form_multipart('/', 'post',
              self.input('file', type='file'),
              self.input_submit()
          )
      )
	
  # Uploading file:
  @server.post('/')
  def kek(self):
      if 'file' in self.post:
          file_post = self.post['file']
          with open(file_post['filename'], 'wb') as file:
              file.write(file_post['file'])
              file.close()
          return self.redirect('/?status=Success.')
      else:
          return self.redirect('/?status=Fail.')

  # Starting server:
  server.start()
  
================
Complex Examples
================

Interactive chat using AJAX and jQuery
--------------------------------------
Chat that updates using AJAX after receiving new messages.

.. code-block:: python

  # Connecting Perver:
  from perver import Perver

  # Importing JSON, used for AJAX posts:
  from json import dumps as json_dump

  # Making new instance:
  server = Perver()

  # Messages:
  messages = []
  # Notice: They will not be saved after shutting down the server.

  # JQuery, used for AJAX requests:
  jquery_url = '<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.1.0/jquery.min.js"></script>'

  # Updating AJAX script using JQuery:
  script = '''
  <script>
      update_time = 2000;
      function update_messages() {
          $.ajax({
              type: 'GET',
              url: '/messages',
              success: function(data) {
                  html_msg = "";
                  msg = $.parseJSON(data);
                  for (var i = 0; i < msg.length; i++) {
                      single_msg = ['<b>', msg[i][0], '-', msg[i][1], '</b>: ', msg[i][2], '<br>'];
                      html_msg = html_msg.concat(single_msg.join(''));
                  }
                  $('#messages').html(html_msg);
              },
              complete: function(data) {
                  setTimeout(update_messages, update_time);
              }
          });
      }
      setTimeout(update_messages, update_time);
  </script>
  '''
  
  # Displaying form:
  @server.get('/')
  def show_messages(self):
  
      # Composing messages list into string with <br> separators:
      html_messages = '<br>'.join(['<b>%s - %s</b>:%s' % info for info in messages])
      html_messages = '<div id="messages">%s</div>' % html_messages
	
      # Building HTML:
      return self.html(
          head = '\r\n'.join(['<title>Perverted Chat!</title>', jquery_url, script]),
          body = '\r\n'.join([self.form('/', 'post',
              self.input('message', placeholder='Your message'),
              self.input_submit('Send message!')
          ), html_messages])
      )
      
  # Retrieving messages list, used in ajax:
  @server.get('/messages')
  def get_messages(self):
      return json_dump(messages)
      
  # Processing form:
  @server.post('/')
  def post_message(self):
      if 'message' in self.post and len(self.post['message']) > 0:
          messages.append((self.time, self.id, self.post['message']))
      return self.redirect('/')
      
  # Starting server:
  server.start()