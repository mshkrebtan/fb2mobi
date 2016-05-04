This program is based on fb2conv program published by dnkorpushov on [the-ebook.org](http://www.the-ebook.org/forum/viewtopic.php?t=28447&postdays=0&postorder=asc&start=0) site.

Original program (being Python 2) did not work well under Windows when non-russian system codepage was selected for non-Unicode programs. 
In order to improve the situation I had to port it to Python 3 (3.5.1 at the moment). As I am only using it as a companion converter from [MyHomeLib](http://home-lib.net/) 
it lost number of features and gained some bug fixes...

Here is brief list of changes:

* Lost UI functionality
* All messages and profile descriptions got translated to English
* Fixed all problems I was aware of at the moment (see git log)
* Added ability to apply xslt transformation from external file to fb2 before further processing
* Added xslt extension "katz_tr" to speedup and simplify transformation of direct speech in dialogs
* Added some rudimentary epub processing (like title rewriting based on calibre metadata and hyphenation)
* Switched hyphenator to hyphen which uses properly maintained dictionaries from LibreOffice, so now many languages are supported and you could add more
* Added support for "inline" footnotes
* Added support for MOBI post-processing and optimization
* Added cover and thumbnail image optimization
* Made cover size user configurable
* Added support for latest Kidle firmware (>= 5.7.2)
* Added simple tool to generate simple thumbnails on Kindle devices

Program uses source code (modified) from following projects released under GPL:

* [KindleUnpack](https://github.com/kevinhendricks/KindleUnpack)

Enjoy!
