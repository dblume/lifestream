# Lifestream

![shortcut](https://dblume.github.io/images/all_of_lifestream.gif)

This is the code for [David Blume's lifestream project](https://david.dlma.com/lifestream/).
It was [started in 2008](https://www.plurk.com/p/2lrqa), so it uses Python 2.

I have a [blog post describing it in better detail](https://david.dlma.com/blog/my-lifestream).

![shortcut](https://dblume.github.io/images/all_of_lifestream_annotated.gif)

## What is a lifestream?

This kind of lifestream is an aggregation of your user activity feeds from 
across the internet. Essentially, it can be thought of as an automatic online
diary. It writes itself.

## The basic idea

This script is run on a recurring basis by a cronjob or something similar,
and it reads a bunch of RSS or Atom feeds, and from those it aggregates the
entries into a useful website.

## The Feeds

The feeds read in by the lifestream are grouped into categories. The groupings
don't always make sense, and I may change them.

### Links

These are the feeds where I am usually noting some a site's links or some way
I've interacted with that site.

* Amazon Wishlist
* Blippr (a microblogging service for user reviews)
* Crunchyroll
* Digg
* GoodReads
* LibraryThing
* Netflix DVDs
* Pinboard.in
* Pownce

### Journals

My longer form posts.

* David's Personal Blog
* Dokuwiki
* Facebook
* Google+
* LiveJournal
* My Dilemma (WordPress)
* RPS
* Vox
* Wordpress.com

### Messages

These are the feeds of short messages I made.

* David's Personal Tasks (task.dlma.com)
* David's Work Tasks
* Jaiku
* Plurk
* Twitter

### Songs and Audio

Things I've listened to.

* Last.FM
* Overcast (Podcasts)

### Visual: Pictures and Video

* Flickr
* Hulu
* Instagram
* Tumblr
* YouTube
* YouTube Favorites

### Location

* FourSquare

## This is not good code. It never was

1. It's Python 2. Nowadays don't write code in Python 2.
2. I didn't know about the Python [logging](https://docs.python.org/3/library/logging.html) module when I wrote it.
3. It's very bespoke code for one special use-case.

## My, how things change in 15 years

When this code was originally written, it was tracking DVDs mailed to me from
Netflix, and songs I listened to on my iPhone as tracked in last.fm.

Nowadays, it seems I listen to more podcasts than songs and I watch anime on Crunchyroll.

## This is an archive

While the lifestream is still running as of this writing, it's not being
actively maintained.

## Is it any good?

[Yes](https://news.ycombinator.com/item?id=3067434).

