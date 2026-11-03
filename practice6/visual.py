import json

import cv2

from decompose import iter_frames

COCO_RU = {
    "person": "человек", "bicycle": "велосипед", "car": "машина", "motorcycle": "мотоцикл", "airplane": "самолёт",
    "bus": "автобус", "train": "поезд", "truck": "грузовик", "boat": "лодка", "traffic light": "светофор",
    "fire hydrant": "гидрант", "stop sign": "знак стоп", "parking meter": "паркомат", "bench": "скамейка",
    "bird": "птица", "cat": "кошка", "dog": "собака", "horse": "лошадь", "sheep": "овца", "cow": "корова",
    "elephant": "слон", "bear": "медведь", "zebra": "зебра", "giraffe": "жираф", "backpack": "рюкзак",
    "umbrella": "зонт", "handbag": "сумка", "tie": "галстук", "suitcase": "чемодан", "frisbee": "фрисби",
    "skis": "лыжи", "snowboard": "сноуборд", "sports ball": "мяч", "kite": "воздушный змей",
    "baseball bat": "бейсбольная бита", "baseball glove": "бейсбольная перчатка", "skateboard": "скейтборд",
    "surfboard": "сёрфборд", "tennis racket": "теннисная ракетка", "bottle": "бутылка", "wine glass": "бокал",
    "cup": "чашка", "fork": "вилка", "knife": "нож", "spoon": "ложка", "bowl": "миска", "banana": "банан",
    "apple": "яблоко", "sandwich": "сэндвич", "orange": "апельсин", "broccoli": "брокколи", "carrot": "морковь",
    "hot dog": "хот-дог", "pizza": "пицца", "donut": "пончик", "cake": "торт", "chair": "стул", "couch": "диван",
    "potted plant": "растение в горшке", "bed": "кровать", "dining table": "обеденный стол", "toilet": "унитаз",
    "tv": "телевизор", "laptop": "ноутбук", "mouse": "компьютерная мышь", "remote": "пульт", "keyboard": "клавиатура",
    "cell phone": "телефон", "microwave": "микроволновка", "oven": "духовка", "toaster": "тостер",
    "sink": "раковина", "refrigerator": "холодильник", "book": "книга", "clock": "часы", "vase": "ваза",
    "scissors": "ножницы", "teddy bear": "плюшевый мишка", "hair drier": "фен", "toothbrush": "зубная щётка",
}


def ru(name):
    return COCO_RU.get(name, name)


class YoloDetector:
    def __init__(self, model_path="yolov8n.pt", min_conf=0.25):
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.min_conf = min_conf

    def __call__(self, frame):
        res = self.model.predict(frame, conf=self.min_conf, verbose=False)[0]
        out = []
        for b in res.boxes:
            out.append({"c": self.model.names[int(b.cls)], "p": round(float(b.conf), 3),
                        "box": [int(v) for v in b.xyxy[0].tolist()]})
        return out


def scene_signature(frame):
    small = cv2.resize(frame, (160, 90))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
    return cv2.normalize(h, h).flatten()


def analyze_frames(video_path, out_path, detector, interval):
    n, prev = 0, None
    tmp = out_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for t, frame in iter_frames(video_path, interval):
            sig = scene_signature(frame)
            corr = None if prev is None else round(float(cv2.compareHist(prev, sig, cv2.HISTCMP_CORREL)), 3)
            prev = sig
            dets = detector(frame) if detector else []
            f.write(json.dumps({"t": round(t, 2), "scene_corr": corr, "dets": dets}, ensure_ascii=False) + "\n")
            n += 1
    tmp.replace(out_path)
    return n


def read_frames(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]
