# PDF Data Scrapers 
# Introduction - What are these projects?
This repository contains 2 different data scrapers. They all follow the same objective, extract all the data (name, price) of various commercial catalogs from 2 portuguese stores (Aldi and Continente). 

# Why extract the data out of commercial catalogs?
It may seem odd going for this approach in a way of learning but, if you think about it, it is not as easy as it may seem. 
- The whole catalog, for starters, can be huge, and its important to have a very well optimized script that can sort, find and catch all important data. 
Not all the catalog follows the same rules (size, color, spacing) so you have to make another script to keep an eye open to all the data that can and will be important to the user.
- The download isnt always just behind a button: The Crawler of the project is one of the main aspects, its an automatic bot who enters the website, scans the HTML code (buttons, tags, divs, ...) and finds the right catalog. Inside the catalog it needs to find the download link itself.
- The catalogs are not always on PDF : In some of the presented Scrapers the method is not PDF, it is IPaper.


