from src.session import SessionManager
from src.imhentai_api import IMHentaiAPI

def main():
    sm = SessionManager()
    api = IMHentaiAPI(sm.get_session())
    print('Authenticated?', sm.is_authenticated())

    preset_tags = ['feminization','genderbender','gender change','transformation','crossdressing']
    print('Searching...')
    galleries = api.search(tags=preset_tags, max_results=5, max_pages=1)
    print('Found', len(galleries), 'galleries')
    for idx, g in enumerate(galleries):
        print('\nGallery', idx+1)
        print('Title:', repr(g.title))
        print('URL:', g.url)
        print('Tags:', g.tags)
        print('Pages:', g.pages)
        imgs = api.get_gallery_images(g.url)
        print('Images found:', len(imgs))
        for i, img in enumerate(imgs[:5]):
            print(' ', i+1, img)
        break

if __name__ == '__main__':
    main()
