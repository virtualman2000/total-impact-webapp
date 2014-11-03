import math
internet_users = {
    'BD': 10178672,
    'BE': 9199067,
    'BF': 745132,
    'BG': 3854978,
    'BA': 2600099,
    'BB': 213483,
    'BM': 61967,
    'BN': 269470,
    'BO': 4215124,
    'BH': 1198953,
    'BI': 132112,
    'BJ': 505850,
    'BT': 225430,
    'JM': 1026269,
    'BW': 303171,
    'WS': 29126,
    'BR': 103386753,
    'BS': 271709,
    'BY': 5127732,
    'BZ': 105212,
    'RU': 88108914,
    'RW': 1617838,
    'RS': 1212131,
    'LT': 2023550,
    'LU': 509395,
    'LR': 197527,
    'RO': 9934776,
    'GW': 52831,
    'GU': 107991,
    'GT': 3047235,
    'GR': 6604646,
    'GQ': 124150,
    'JP': 109829560,
    'GY': 625338,
    'GE': 1929543,
    'GD': 37063,
    'GB': 57587449,
    'GA': 153797,
    'GN': 187923,
    'GM': 258899,
    'GL': 37165,
    'KW': 1543231,
    'GH': 3186265,
    'OM': 589006,
    'JO': 2854878,
    'HR': 2838575,
    'HT': 1093650,
    'HU': 7189746,
    'HK': 5333125,
    'HN': 582925,
    'AD': 74464,
    'PR': 2671548,
    'PW': 7976,
    'PT': 6495079,
    'KN': 43352,
    'PY': 1555757,
    'PA': 1657728,
    'PF': 157240,
    'PG': 475882,
    'PE': 11907236,
    'PK': 19853542,
    'PH': 36405622,
    'PL': 24216252,
    'ZM': 2238950,
    'EE': 1059746,
    'EG': 62214271,
    'ZA': 25908193,
    'EC': 6350813,
    'AL': 1666945,
    'AO': 4101079,
    'KZ': 9200254,
    'ET': 8398573,
    'ZW': 2617684,
    'KY': 43300,
    'ES': 33386445,
    'ER': 56998,
    'ME': 352945,
    'MD': 1736792,
    'MG': 504346,
    'MF': 11921,
    'MA': 12586779,
    'MC': 34312,
    'UZ': 11552100,
    'MM': 18182110,
    'ML': 351937,
    'MO': 372674,
    'MN': 502515,
    'MH': 17231,
    'MK': 1289580,
    'MU': 505558,
    'MT': 291699,
    'MW': 883578,
    'MV': 134936,
    'MP': 20536,
    'MR': 241172,
    'AU': 19198647,
    'UG': 6087777,
    'MY': 25069372,
    'MX': 53165660,
    'VU': 96384,
    'FR': 54090388,
    'FI': 4977840,
    'FJ': 326875,
    'FM': 28786,
    'FO': 44522,
    'NI': 942474,
    'NL': 11037718,
    'NO': 4832695,
    'NA': 320160,
    'NC': 172920,
    'NE': 303131,
    'NG': 65973831,
    'NZ': 3370536,
    'NP': 3697061,
    'CI': 7746998,
    'CH': 3081658,
    'CO': 24982166,
    'CN': 621680039,
    'CM': 1424253,
    'CL': 11717105,
    'CA': 13406683,
    'CG': 293543,
    'CF': 161574,
    'CD': 1485300,
    'CZ': 7797502,
    'CY': 746947,
    'CR': 2249458,
    'CW': 58533,
    'CV': 187086,
    'CU': 2896272,
    'SZ': 308629,
    'SY': 5985534,
    'SX': 15134,
    'KG': 1338362,
    'KE': 17297939,
    'SS': 2701819,
    'SR': 201689,
    'KI': 11770,
    'KH': 908110,
    'SV': 1465234,
    'KM': 47769,
    'ST': 44388,
    'SK': 4216637,
    'KR': 19149934,
    'SI': 1497469,
    'KP': 9493228,
    'SO': 157433,
    'SN': 2953855,
    'SM': 15975,
    'SL': 103565,
    'SC': 44943,
    'SB': 44898,
    'SA': 10993122,
    'SG': 3941416,
    'SE': 9092166,
    'SD': 8617897,
    'DO': 4775326,
    'DM': 42481,
    'DJ': 82928,
    'DK': 5312233,
    'DE': 67691181,
    'YE': 4881476,
    'AT': 6831464,
    'DZ': 25638844,
    'US': 266180482,
    'LV': 1514758,
    'UY': 1979503,
    'LB': 3149509,
    'LC': 12998,
    'LA': 846215,
    'TV': 3654,
    'TT': 855654,
    'TR': 34656346,
    'LK': 5962485,
    'LI': 34635,
    'TN': 4768286,
    'TO': 36863,
    'TL': 12960,
    'TM': 503046,
    'TJ': 1313253,
    'LS': 103723,
    'TH': 19392839,
    'TG': 306764,
    'TD': 294982,
    'TC': 12621,
    'LY': 1023250,
    'VC': 56873,
    'AE': 8224593,
    'VE': 16692458,
    'AG': 57050,
    'AF': 1802548,
    'IQ': 3074407,
    'VI': 47445,
    'IS': 311848,
    'IR': 24318410,
    'AM': 1378150,
    'IT': 34976838,
    'VN': 39382207,
    'AS': 21035,
    'AR': 24826301,
    'IM': 32751,
    'IL': 5706055,
    'AW': 81196,
    'IN': 477470109,
    'TZ': 2167137,
    'AZ': 5527543,
    'IE': 3595701,
    'ID': 39528742,
    'UA': 20376020,
    'QA': 1849878,
    'MZ': 1395022
}


def events_per_1m_internet_users(event_counts, adjust_for_access=False):  # { <country_code>: <event_count>, ...}
    ret = {}
    for country_code, my_event_count in event_counts.iteritems():
        my_internet_users_millions = get_internet_users_millions(country_code, adjust_for_access)
        if my_internet_users_millions is not None:
            ret[country_code] = my_event_count / my_internet_users_millions

    return ret


def get_internet_users_millions(country_code, adjust_for_access=False):
    try:
        my_internet_users = internet_users[country_code]
    except KeyError:
        return None

    if adjust_for_access and country_code == "CN":
        my_internet_users *= .001  # adjust for Great Firewall

    return math.ceil(my_internet_users / 1000000.0)




def internationality(event_counts):
    counts_dict = events_per_1m_internet_users(event_counts, True)

    counts = counts_dict.values()
    num_countries = len(internet_users.keys())

    # pad list with zeros so there's one item per country
    # from http://stackoverflow.com/a/3438818
    padded_counts = counts + [0] * (num_countries - len(counts))

    try:
        gini_as_percent = (1 - gini(padded_counts)) * 100
    except ZeroDivisionError:
        gini_as_percent = None

    return gini_as_percent


# from http://planspace.org/2013/06/21/how-to-calculate-gini-coefficient-from-raw-data-in-python/
def gini(list_of_values):
    sorted_list = sorted(list_of_values)
    height, area = 0, 0
    for value in sorted_list:
        height += value
        area += height - value / 2.
    fair_area = height * len(list_of_values) / 2
    return (fair_area - area) / fair_area

