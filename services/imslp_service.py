import requests
from typing import List, Dict, Optional

class ImslpService:
    BASE_URL = "https://imslp.org/api.php"

    def search_scores(self, keyword: str, limit: int = 20) -> List[Dict]:
        """
        Search IMSLP for scores by keyword.
        """
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': keyword,
            'srwhat': 'text',
            'srlimit': limit,
            'format': 'json'
        }
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data.get('query', {}).get('search', []):
                results.append({
                    'title': item['title'],
                    'snippet': item['snippet'],
                    'pageid': item['pageid']
                })
            return results
        except Exception as e:
            print(f"Error searching IMSLP: {e}")
            return []

    def get_violin_scores(self, limit: int = 50) -> List[Dict]:
        """
        Get scores specifically from the Violin category.
        """
        params = {
            'action': 'query',
            'list': 'categorymembers',
            'cmtitle': 'Category:For violin',
            'cmlimit': limit,
            'cmnamespace': 0,
            'format': 'json'
        }
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data.get('query', {}).get('categorymembers', []):
                results.append({
                    'title': item['title'],
                    'pageid': item['pageid']
                })
            return results
        except Exception as e:
            print(f"Error fetching violin scores: {e}")
            return []

    def get_download_urls(self, work_title: str) -> List[Dict]:
        """
        Get direct download URLs for PDF/MusicXML files for a given work.
        """
        # Step 1: Get images (files) for the page
        params1 = {
            'action': 'query',
            'prop': 'images',
            'titles': work_title,
            'format': 'json'
        }
        try:
            response = requests.get(self.BASE_URL, params=params1, timeout=10)
            data = response.json()
            pages = data.get('query', {}).get('pages', {})
            if not pages:
                return []
            
            page_id = list(pages.keys())[0]
            if 'images' not in pages[page_id]:
                return []
            
            files = pages[page_id]['images']
            urls = []

            # Step 2: Get URL for each file
            for file_info in files:
                filename = file_info['title']
                # Filter for PDF or XML/MXL
                if not (filename.endswith('.pdf') or filename.endswith('.xml') or filename.endswith('.mxl')):
                    continue

                params2 = {
                    'action': 'query',
                    'titles': filename,
                    'prop': 'imageinfo',
                    'iiprop': 'url',
                    'format': 'json'
                }
                resp2 = requests.get(self.BASE_URL, params=params2, timeout=5)
                data2 = resp2.json()
                pages2 = data2.get('query', {}).get('pages', {})
                page_id2 = list(pages2.keys())[0]
                
                if 'imageinfo' in pages2[page_id2]:
                    url = pages2[page_id2]['imageinfo'][0]['url']
                    # Handle protocol-relative URLs
                    if url.startswith('//'):
                        url = 'https:' + url
                    urls.append({
                        'filename': filename,
                        'url': url
                    })
            return urls
        except Exception as e:
            print(f"Error fetching download URLs: {e}")
            return []
