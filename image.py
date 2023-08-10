import oss2
from io import BytesIO
from PIL import Image


class AliyunOss(object):

    def __init__(self):
        self.access_key_id = "LTAI5tK5oGVY4Y77TzSTp4gi"   # 从阿里云查询到的 AccessKey 的ID
        self.access_key_secret = "56EKrHI7rwriGpZbGionC8UHlMnHvu"  # 从阿里云查询到的 AccessKey 的Secret
        self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self.bucket_name = "3090bot"  # 阿里云上创建好的Bucket的名称
        self.endpoint = "oss-cn-beijing.aliyuncs.com"  # 阿里云从Bucket中查询到的endpoint
        self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)

    def put_object(self, name, file):
        self.bucket.put_object(name, file)
        return "https://{}.{}/{}".format(self.bucket_name, self.endpoint, name)
    
def upload_img(image,name):
    buf = BytesIO()
    image.save(buf,'png')
    image_stream = buf.getvalue()
    return AliyunOss().put_object(f"img/{name}",image_stream)
