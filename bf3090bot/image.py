import oss2
from io import BytesIO
from PIL import Image
from .utils import OSS_ACESS_KEY_ID, OSS_ACESS_KEY_SECRET, OSS_BUCKET_NAME, OSS_ENDPOINT, AsyncSingletonMeta

class AliyunOss(metaclass=AsyncSingletonMeta):

    def __init__(self):
        self.access_key_id = OSS_ACESS_KEY_ID   # 从阿里云查询到的 AccessKey 的ID
        self.access_key_secret = OSS_ACESS_KEY_SECRET  # 从阿里云查询到的 AccessKey 的Secret
        self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self.bucket_name = OSS_BUCKET_NAME  # 阿里云上创建好的Bucket的名称
        self.endpoint = OSS_ENDPOINT  # 阿里云从Bucket中查询到的endpoint
        self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)

    def put_object(self, name, file):
        self.bucket.put_object(name, file)
        return "https://{}.{}/{}".format(self.bucket_name, self.endpoint, name)
    
async def upload_img(image: Image, name: str):
    buf = BytesIO()
    image.save(buf,'png')
    image_stream = buf.getvalue()
    aliyunoss = await AliyunOss()
    return aliyunoss.put_object(f"img/{name}",image_stream)
