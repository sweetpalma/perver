==============================
🐍 Perver: Async Web Framework 
==============================

    Copyright 2016 SweetPalma <sweet.palma@yandex.ru>
    
.. image:: https://raw.githubusercontent.com/SweetPalma/Perver/master/logo.png
  :target: https://github.com/SweetPalma/Perver

Perver is a small experimental web-framework with embedded async server. You just `download it <https://raw.githubusercontent.com/SweetPalma/Perver/master/perver.py>`_, include it and run it. And it just works - no other dependencies but Python Standart Library. Sounds easy? Take a look at example then:

Installation
============
`Download <https://raw.githubusercontent.com/SweetPalma/Perver/master/perver.py>`_ this into your working directory. Dont forget, you need Python 3.4 or newer. Done, you're ready to go.

P.S. If your browser doesn't download it, simply displaying a text file - press on that link with right mouse button and choose "Save As".

Example: "Hello World" in perverted style
=========================================
.. code-block:: python

  from perver import Perver
  server = Perver()

  @server.route('/')
  def page_main(self):
      return self.redirect('/hello/perverts')
	
  @server.route('/hello/{name}')
  def page_hello(self, name):
      return 'Hello, ' + name

  server.start('', 80)
  
Make a script or paste that in your Python console. Now open `your localhost <http://localhost>`_ - and magic will happen! You can even type `something different <http://localhost/hello/world>`_ - if you like classical 'Hello World' more.

Features?
=========
* **Server:** You don't need any other server to test your code. Perfect for small projects and prototyping.
* **Asynchronous:** It uses non-blocking IO, forget about creepy one-client issues in small frameworks.
* **Routing:**: Requests to function-call mapping for clean and dynamic URLs.
* **Utilities:** Batteries included - POST/GET, cookies, headers and other HTTP-related data.

License
=======
See the `LICENSE <https://raw.githubusercontent.com/SweetPalma/Perver/master/LICENSE>`_ file for more information. And don't use my perverted python logo for anything else, please.

Credits
=======
Hardly inspired by `BottlePy <https://github.com/bottlepy/bottle/>`_.

Want more?
==========
`Read reference with examples <https://github.com/SweetPalma/Perver/blob/master/REFERENCE.rst>`_.
