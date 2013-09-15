## Omnibust - A universal cachebusting script

A language and framework agnostic cachbusting script.

Omnibust will scan the files of your web project for static resources
(js, css, png) and also for urls in your sourcecode (html, js, css, py,
rb, etc.) which reference these resources. It will add or update a
cachebust parameter on any such urls based on the static resources they
reference.

Requires python >= 2.6 or python >= 3.2.
[![Build Status](https://travis-ci.org/mbarkhau/omnibust.png)](https://travis-ci.org/mbarkhau/omnibust)


### Installation

    $ pip install omnibust

Or

    $ wget https://raw.github.com/mbarkhau/omnibust/master/omnibust.py
    $ chmod +x omnibust.py
    $ cp omnibust.py /usr/local/bin/omnibust

Check that it worked
    
    $ omnibust --help


### Usage

Project setup:

    $ cd your/project/directory
    $ omninust init

This will write the `.omnibust` file, which you can take a look at and
update if some of your urls are not being found.

If this doesn't find all references to static files, or doesn't find
the static files themselves, you will have to adjust `static_dirs` and
`code_dirs` in your `omnibust.cfg` (see below). Please also consider
opening a ticket on [https://bitbucket.org/mbarkhau/omnibust], as 
omnibust should work out of the box for as many projects as reasonably
possible.

The `rewrite` option will add a `_cb_` to every static url it can
find and associate with a static file in the project directory.

CAUTION: Since `rewrite` will modify your source files, you should
commit or backup your files and run omnibust with `--no-act` first to
make certain it won't modify anything in the wrong way.

    $ omnibust status --querystring
    $ omnibust rewrite --querystring

From now on you simply run omnibust rewrite on your project directory
and it will only update urls with an existing `_cb_` parameter.

    $ omnibust rewrite


### Options and Configuration


Explicitly specify files
TODO: parameter configuration


### Dynamic URLs and Multibust

Some URLs may not be found with `omnibust init`, esp. if they are not preceded
by something like `src=` or `url(`, and of course URLs which are dynamically
created during runtime cannot automatically be found at all.

You can help omnibust find these by manually marking them with `_cb_`. After
this, you can run `omnibust update` will expand the marker to a full cachbust
parameter.

The `multibust` configuration option allows for a limited form of dynamic URLs.
Omnibust will expand any URL using the configured `multibust` mapping. If a
multibust key (typically a template variable) is found in an URL, it is 
expanded using the corresponding associated multibust values. The search for
static resources is then based on the expanded URLs.

Given the configuration

    "multibust": {"{{ language }}": ["en", "de", "fr", "jp", "es"]}

And the following URL

    <img src="i18n_image_{{ language }}_cb_0123abcd.png" />

The following static resources may be matched for this URL

    /static/i18n_image_en.png
    /static/i18n_image_de.png
    ...

If any of these files is modified, the cachebust parameter will be updated. 
This method is safe (in that any change to the static resource results in
cache invalidation) and convenient (in that one url can be used to reference
semantically similar files), but it does mean that some cached files will be
invalidated that were still valid. If this is a problem for you, all static
files will have to be referenced explicitly. You could for example create a
mapping of the form

    i18n_images = {
        'en': "/static/i18n_image_en_cb_0123abcd.png",
        'de': "/static/i18n_image_de_cb_0123abcd.png",
        ...
    }

And reference it for example from a jinja2 template like this

    <img src="{{ i18n_image[language] }}" />


### Webserver Setup

In order for browsers to cache and reuse your static resources, your
webserver must set appropriate cache headers. Here are some example
configuration directives for common webservers.


### Filename Based Cachbusting

Omnibust defaults to query parameter `app.js?_cb_=0123abcd` based
cachbusting, but it can also rewrite the filenames in urls to the form
`app_cb_0123abcd.js`. This is useful since URLs with query parameters are not
cached by all browsers in all situations, even if all caching headers are
provided correctly [needs reference]. TODO: check if there are browsers where
a cached resource will be used even if the query string changes.

Putting a cachebust parameter in the filename of a URL will guarantee that your
static resource is loaded when it has changed and it will be cached in more
situations. The downside is, that your urls now have filenames which reference
files that don't actually exist! (Assuming you don't create them, which would
be quite laborious and error prone.) The sollution is to have your webserver
rewrite the urls of requests it recieves, by stripping out the cachebust
parameter, and serving the correct static resource. Here are some
configuration directives for common webservers.

	# Nginx

	location ~* ^/static/(.+?)_cb_\w+(\.\w+)$ {
	    alias /srv/www/static/$1$2;
	    add_header Vary Accept-Encoding;
	    expires max;
	}
 
	# Apache

	RewriteRule ^/static/(.+?)_cb_\w+(\.\w+)$ /static/$1$2
