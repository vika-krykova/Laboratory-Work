from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    data_dir: str = "data"
    out_dir: str = "out"

    max_height: int = 720 

    frame_interval: Optional[float] = None 

    yolo_model: str = "yolov8n.pt"
    yolo_min_conf: float = 0.25  
    yolo_conf: float = 0.4  

    whisper_model: str = "base"
    language: Optional[str] = "ru" 
    no_speech_max: float = 0.6 

    loud_z: float = 2.0      
    loud_floor_db: float = -35.0  
    scene_corr: float = 0.6 
    obj_min_duration: float = 3.0  
    obj_max_gap: float = 2.0 

    topic_method: str = "kmeans"
    max_k: int = 6
