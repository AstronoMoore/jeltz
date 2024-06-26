import requests
import sys
import json
import configparser
import pandas as pd
from astropy.time import Time
from lasair import LasairError, lasair_client as lasair
import urllib.parse
from urllib.parse import urlencode
from astropy.time import Time
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.table import Table

TNS_API_URL = 'https://www.wis-tns.org/api/get/object'

def get_TNS_api_key():
    try:
        config = configparser.ConfigParser()
        config.read('settings.ini')
        if 'TNS_API_KEY' in config['API']:
            key = config['API']['TNS_API_KEY']
            return key
        else:
            print("Error: TNS API key not found in settings.ini")
            return None
    except FileNotFoundError:
        print("Error: settings.ini file not found")
        return None
    

def get_atlas_login_keys():
    try:
        config = configparser.ConfigParser()
        config.read('settings.ini')
        if 'ATLAS' in config:
            username = config['ATLAS']['ATLAS_USERNAME']
            password = config['ATLAS']['ATLAS_PASS']
            return username, passwords
        else:
            print("Error: ATLAS not found in settings.ini")
            return None
    except FileNotFoundError:
        print("Error: settings.ini file not found")
        return None


def get_LASAIR_TOKEN():
    """
    # fetching the token from the settings.ini file
    """
    config = configparser.ConfigParser()
    config.read('settings.ini')
    return config['API']['LASAIR_TOKEN']

def tns_lookup(tnsname):
    """
    Lookup TNS information for the given object name.
    """
    try:
        try:
            api_key = get_TNS_api_key()
        except Exception as e:
            print(f"Error reading TNS API key: {e}")
        data = {
            'api_key': api_key,
            'data': json.dumps({
                "objname": tnsname,
                "objid": "",
                "photometry": "1",
                "spectra": "1"
            })
        }
        response = requests.post(TNS_API_URL, data=data, headers={'User-Agent': 'tns_marker{"tns_id":104739,"type": "bot", "name":"Name and Redshift Retriever"}'})
        response.raise_for_status()  # Raise an exception
        json_data = response.json()
        object_TNS_data = json_data['data']['reply']
        tns_object_info = {key: [value] for key, value in object_TNS_data.items()}
        return tns_object_info
    except Exception as e:
        print(f"fetching TNS info caused an error: {e}")
        return None

def fetch_atlas():
    atlasurl = 'https://fallingstar-data.com/forcedphot'
    response = requests.post(url=f"{atlasurl}/api-token-auth/",data={'username':username,'password':password})
    if response.status_code == 200:
        token = response.json()['token']
        print(f'Token: {token}')
        headers = {'Authorization':f'Token {token}','Accept':'application/json'}
    else:
        raise RuntimeError(f'ERROR in connect_atlas(): {response.status_code}')
        print(resp.json())
    return headers

def fetch_ztf(ztf_name):
    L = lasair(get_LASAIR_TOKEN(), endpoint = "https://lasair-ztf.lsst.ac.uk/api")

    """
    Fetch ZTF data through LASAIR.

    Args:
    - ztf_name (str): The name of the ZTF object to fetch data for.
    - api_client: An instance of the LASAIR API client.

    Returns:
    - pd.DataFrame: DataFrame containing the processed ZTF data.
    """

    try:
        # Fetch data from LASAIR
        object_list = [ztf_name]
        response = L.objects(object_list)
        
        # Create a dictionary of lightcurves
        lcs_dict = {}
        for obj in response:    
            lcs_dict[obj['objectId']] = {'candidates': obj['candidates']}
        
        # process and format
        data = pd.DataFrame(lcs_dict[obj['objectId']]['candidates'])
        data = data[data['isdiffpos']=='t']
        data_ouput = data.filter(['mjd','fid','magpsf','sigmapsf'])
        # Adding filter information
        replacement_values = {1: 'g', 2: 'r'}
        data_ouput['fid'] = data_ouput['fid'].replace(replacement_values)
        data_ouput.insert(len(data_ouput.columns),'telescope','ZTF')
        data_ouput = data_ouput.rename(columns={"fid": "band"})
        data_ouput = data_ouput.rename(columns={"magpsf": "magnitude"})
        data_ouput = data_ouput.rename(columns={"sigmapsf": "e_magnitude"})
        data_ouput = data_ouput.rename(columns={"mjd": "time"})

        return data_ouput

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def fetch_ztf_cone(ra, dec, radius):
    L = lasair(get_LASAIR_TOKEN(), endpoint = "https://lasair-ztf.lsst.ac.uk/api")
    """
    Fetch ZTF data within by cone search
    """

    try:
        # Fetch data from LASAIR with cone searchs
        response = L.cone(ra, dec, radius=radius, requestType='all')
        
        # Gather ZTF object names
        ztf_object_names = [obj['object'] for obj in response]
        
        # Fetch ZTF data for each obj
        dfs = [fetch_ztf(object_name) for object_name in ztf_object_names]
        data_output = dfs

        data_output = pd.concat(dfs, ignore_index=True)

        return data_output

    except Exception as e:
        print(f"An error occurred during ZTF cone search: {e}")
        return None
    
def gaia_e_mag(g_mag):
    """
    Calculate Gaia error in mag 
    """
    e_mag = 3.43779 - (g_mag / 1.13759) + (g_mag / 3.44123)**2 - (g_mag / 6.51996)**3 + (g_mag / 11.45922)**4
    return e_mag

def fetch_gaia(gaia_name):
    """
    Fetch GAIA data
    """
    try:

        # Encode GAIA name for URL
        website = f'http://gsaweb.ast.cam.ac.uk/alerts/alert/{gaia_name}/lightcurve.csv/'
        # Read data from URL
        data = pd.read_csv(website, skiprows=1)
                
        # Clean data
        data = data[(data['averagemag'] != 'untrusted') & data['averagemag'].notna()]
        # changing to MJD and renaming columns
        data['time'] = Time(data['JD(TCB)'], format='jd').mjd
        data['band'] = 'G'
        data['telescope'] = 'Gaia'
        data.rename(columns={"averagemag": "magnitude"},inplace=True)
        # Calculate Gaia error in the magnitudes
        data['e_magnitude'] = data.apply(lambda row: gaia_e_mag(float(row['magnitude'])), axis=1)
        # filtering columns
        data = data.filter(['time', 'band', 'magnitude', 'e_magnitude', 'telescope'])
        
        return data
    except Exception as e:
        print(f"An error occurred while fetching GAIA data: {e}")
        return None
    
def fetch_neowise(ra, dec):    
    skycoord = SkyCoord(ra,dec,unit="deg")
    url =  "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?catalog=neowiser_p1bs_psd&spatial=cone&radius=5&radunits=arcsec&objstr=" + skycoord.ra.to_string(u.hour, alwayssign=True) + '+' + skycoord.dec.to_string(u.degree, alwayssign=True) + "&outfmt=1&selcols=ra,dec,mjd,w1mpro,w1sigmpro,w2mpro,w2sigmpro"
    r = requests.get(url)
    table = Table.read(url, format='ascii')
    neowise_master = table.to_pandas()
    neowise_w1 = neowise_master.filter(['mjd','w1mpro','w1sigmpro'])
    neowise_w1.insert(len(neowise_w1.columns),'band','w1')
    neowise_w1 = neowise_w1.rename(columns={"w1mpro": "magnitude"})
    neowise_w1 = neowise_w1.rename(columns={"w1sigmpro": "e_magnitude"})
    neowise_w2 = neowise_master.filter(['mjd','w2mpro','w2sigmpro'])
    neowise_w2.insert(len(neowise_w2.columns),'band','w2')
    neowise_w2 = neowise_w2.rename(columns={"w2mpro": "magnitude"})
    neowise_w2 = neowise_w2.rename(columns={"w2sigmpro": "e_magnitude"})
    neowise = pd.concat((neowise_w1,neowise_w2))
    neowise.insert(len(neowise.columns),'telescope','NEOWISE')
    neowise = pd.concat((neowise_w1,neowise_w2))
    neowise.insert(len(neowise.columns),'telescope','NEOWISE')
    neowise = neowise.rename(columns={"mjd": "time"}).dropna()
    return neowise

def identify_surveys(TNS_information):
    reporting_list = TNS_information['internal_names']
    reporting_list= reporting_list[0].split(',')
    survey_dict = {}

    # Iterate over each string in the list
    for internal_name in reporting_list:
        if 'ATLAS' in internal_name:
            survey_dict['ATLAS'] = internal_name.replace(" ", "") # removing the annoying space before the internal name  
        if 'Gaia' in internal_name:
            survey_dict['Gaia'] = internal_name.replace(" ", "")# removing the annoying space before the internal name 
        if 'ZTF' in internal_name:
            survey_dict['ZTF'] = internal_name.replace(" ", "")# removing the annoying space before the internal name 
        if 'PS' in internal_name:
            survey_dict['PS'] = internal_name.replace(" ", "")# removing the annoying space before the internal name 
        if 'GOTO' in internal_name:
            survey_dict['GOTO'] = internal_name.replace(" ", "")# removing the annoying space before the internal name 
        if 'BGEM' in internal_name:
            survey_dict['BGEM'] = internal_name
    return survey_dict

def marvin(tnsname):
    TNS_info = tns_lookup(tnsname)
    surveys = identify_surveys(TNS_info)

    The_Book = []

    if 'Gaia' in surveys: 
        The_Book.append(fetch_gaia(surveys['Gaia']))
    
    if 'ZTF' in surveys: 
        The_Book.append(fetch_ztf(surveys['ZTF']))

    if 'ZTF' not in surveys:
        The_Book.append(fetch_ztf_cone(TNS_info['radeg'][0],TNS_info['decdeg'][0],0.15))

    The_Book.append(fetch_neowise(TNS_info['radeg'][0], TNS_info['decdeg'][0]))

    combined_data = pd.concat(The_Book, ignore_index=True)

    return combined_data

if __name__ == "__main__":
    print('JELTZ!')
