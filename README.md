# egazette
Modules to be installed:

1. BeautifulSoup 4: https://www.crummy.com/software/BeautifulSoup/

2. python-magic  https://github.com/ahupp/python-magic

3. pypdf2 https://github.com/mstamy2/PyPDF2

Usage:python sync.py   [-l level(critical, error, warn, info, debug)]

                       [-a (all_downloads)]

                       [-m (updateMeta)]

                       [-n (no aggregation of srcs by hostname)]

                       [-r (updateRaw)]

                       [-f logfile]

                       [-t fromdate (DD-MM-YYYY)] [-T todate (DD-MM-YYYY)] 


                       [-s central_weekly -s central_extraordinary -s central
                        -s states -s andhra -s bihar -s chattisgarh
                        -s cgweekly -s cgextraordinary 
                        -s delhi -s delhi_weekly -s delhi_extraordinary
                        -s karnataka
                       ]

                       [-D datadir]


The program will download gazettes from various egazette sites
and will place in a specified directory. Gazettes will be
placed into directories named by type and date. If fromdate or
todate is not specified then the default is your current date.

