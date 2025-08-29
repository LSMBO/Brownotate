import os
import requests

def download_species_image(scientific_name):
    scientific_name = scientific_name.replace(' ', '_').lower()
    scientific_name = scientific_name.capitalize()
    api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{scientific_name}"
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; BrownotateBot/1.2; +https://github.com/LSMBO/Brownotate)'}
    response = requests.get(api_url, headers=headers)
    if response.status_code != 200:
        print("Page not found", api_url, "status code:", response.status_code)
        return "user_download/image_not_found.png"

    data = response.json()
    image_url = data.get('thumbnail', {}).get('source')

    if not image_url:
        print("Image not found")
        return "user_download/image_not_found.png"

    os.makedirs('user_download', exist_ok=True)
    image_response = requests.get(image_url, headers=headers)
    if image_response.status_code == 200:
        image_name = scientific_name + os.path.splitext(image_url)[-1]
        image_path = os.path.join('user_download', image_name)
        with open(image_path, 'wb') as f:
            f.write(image_response.content)
        return image_path
    else:
        return "user_download/image_not_found.png"