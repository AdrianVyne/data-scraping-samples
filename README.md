# data-scraping-samples
 Here I will place data scraping codes publicly since my private codes may have private/ sensitive data that should not be shared


# # Princeton TMX
scripts:
accept_tmx_loads.py and TMX_get_loads.py

story:
I have built connections connected to frieght businesses and this client has a load list that he wants to auto accept at the website "PrincetonTMX"

problem:
Not enough man power to have a person checking the website every now and then to check if there is a desireable load

solution:
having a a script "TMX_get_loads.py" to scrape all the load data in the website PrincetonTMX
If there is a desirable load "accept_tmx_loads.py" constantly checks the scraped data and will auto click to the buttons to accept the load

a desireable load is defined on the location_sets with its locations and a minimum rate to follow. Not all location fields can be entered to find a match of a desireable load.

*note headless is commented out to see how it functions and somehow be notified if a desirable load was accepted


# # 