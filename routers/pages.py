"""Router: pages — các endpoint cùng nhóm chức năng."""
from fastapi import APIRouter
from common import *

router = APIRouter()

@router.get('/', include_in_schema=False)
@router.get('/compare', include_in_schema=False)
def home(): return FileResponse(ROOT/'static'/'index.html')


@router.get('/models/{model}', include_in_schema=False)
def model_page(model:str):
    check_model(model); return home()

