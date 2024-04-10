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


# # Email scraping

story:
emails are sorted out on frieght business to which shipper it is received from and a label is set for it. In this scenario it is set on a labal named "weeks-forest"

problem:
with this business' internal data that processes' a specific file format is accepted to easily integrate with the existing API. Having a bunch of texts from emails will not do this job. Emails are sent to a lot of people which means requets for a specific format is not possible.

solution:
Scarping email and sorting out data with "weeks_forest_loads.py" script

*note:
    • You'll need your own gmail API OAuth credentials from google. 
    • this script can be greatly imporved, one of the things I suggest is to have a more dynamic approach on getting the location data from the email body. A sample email in html format is included for reference.

# # 