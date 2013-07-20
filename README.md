Omnibust - A cachebusting script
================================

A language and framework agnostic cachbusting script. Its only dependency is
python 2.6 or greater.

Omnibust scans your project files for static resources, such as js, css, png
files, and urls which reference these resources in your sourcecode (html, js,
css, py, rb, etc.). It will rewrite any such urls so they have a unique
cachebust parameter, which is based on the modification time and contents of
the static resource files.

Omnibust defaults to query parameter `_cb_=0123abcd` based cachbusting, but it
can also rewrite the filenames in urls to the form  `app_cb_0123abcd.js`. See
[Filename Based Cachbusting] for more info on why you might want to use this.


Installation
============

    $ easy_install omnibust

Or

    $ pip install omnibust

Or

    $ wget https://bitbucket.org/mbarkhau/omnibust/raw/.../omnibust.py
    $ chmod +x omnibust.py
    $ cp omnibust.py /usr/local/bin/omnibust

Check that it worked
    
    $ omnibust --help

Usage
=====

Write omnibust.cfg and show found resources

    $ cd your/project/directory
    $ omninust init

Show all references to static resources.

    $ omnibust scan

If this doesn't find all references to static files, or doesn't find the static
files themselves, you will have to adjust your your omnibust.cfg (see below).

Please also consider opening a ticket on 
[https://bitbucket.org/mbarkhau/omnibust], as we would like to have the script
work out of the box for as many projects as reasonably possible.

Before using rewrite, this would be a good time to commit all your outstanding
changes. If that is done, and the scan shows your relevant resources, you can
have omnibust add cachebust parameters.

    $ omnibust rewrite

From now on you can use the `update` subcommand. This will only rewrite
references which already contain a `_cb_` parameter.

    $ omnibust update


Options and Configuration
=========================


Explicitly specify files


Webserver Setup
===============

In order for browsers to cache and reuse your static resources, your webserver
must set appropriate cache headers. Here are some example configuration
directives for common webservers.


Filename Based Cachbusting
==========================

URLs with query parameters are not cached by all browsers in all situations,
even if all caching headers are provided correctly [needs reference]. TODO: 
check if there are browsers where a cached resource will be used even if the
query string changes.

Putting a cachebust parameter in the filename of a URL will guarantee that your
static resource is loaded when it has changed and it will be cached in more
situations. The downside is, that your urls now have filenames which reference
files that don't actually exist! (Assuming you don't create them, which would
be quite laborious and error prone.) The sollution is to have your webserver
rewrite the urls of requests it recieves, by stripping out the cachebust
parameter, and serving the correct static resource. Here are some
configuration directives for common webservers.


Apache
------

Nginx
-----

Django
------

Flask
-----
