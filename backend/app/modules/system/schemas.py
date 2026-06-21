"""
若茗 PaaS - 部门 + 字典 Pydantic 模型
"""
from pydantic import BaseModel, Field


# ============ 部门模型 ============

class DeptCreate(BaseModel):
    """创建部门"""
    parent_id: int = Field(default=0, description="父部门 ID（0=根部门）")
    name: str = Field(..., min_length=1, max_length=64, description="部门名称")
    sort: int = Field(default=0, ge=0, description="排序")
    leader: str | None = Field(None, max_length=32, description="负责人")
    phone: str | None = Field(None, max_length=20, description="联系电话")
    email: str | None = Field(None, max_length=128, description="邮箱")
    status: int = Field(default=1, ge=0, le=1, description="状态：1正常 0停用")
    remark: str | None = None


class DeptUpdate(BaseModel):
    """更新部门"""
    parent_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=64)
    sort: int | None = Field(None, ge=0)
    leader: str | None = Field(None, max_length=32)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=128)
    status: int | None = Field(None, ge=0, le=1)
    remark: str | None = None


class DeptInfo(BaseModel):
    """部门信息"""
    id: int
    parent_id: int
    name: str
    ancestors: str | None
    level: int
    sort: int
    leader: str | None
    phone: str | None
    email: str | None
    status: int
    tenant_id: int | None
    children: list["DeptInfo"] = []
    remark: str | None

    class Config:
        from_attributes = True


# ============ 字典模型 ============

class DictTypeCreate(BaseModel):
    """创建字典类型"""
    name: str = Field(..., min_length=1, max_length=64, description="字典类型名称")
    code: str = Field(..., min_length=1, max_length=64, description="字典类型编码")
    description: str | None = None
    sort: int = Field(default=0, ge=0, description="排序")
    status: int = Field(default=1, ge=0, le=1, description="状态：1正常 0停用")


class DictTypeUpdate(BaseModel):
    """更新字典类型"""
    name: str | None = Field(None, min_length=1, max_length=64)
    code: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = None
    sort: int | None = Field(None, ge=0)
    status: int | None = Field(None, ge=0, le=1)


class DictTypeInfo(BaseModel):
    """字典类型信息"""
    id: int
    name: str
    code: str
    description: str | None
    sort: int
    status: int
    is_system: bool
    tenant_id: int | None

    class Config:
        from_attributes = True


class DictTypeWithItems(DictTypeInfo):
    """字典类型信息（含字典项）"""
    items: list["DictItemInfo"] = []


class DictItemCreate(BaseModel):
    """创建字典项"""
    type_id: int = Field(..., description="所属字典类型 ID")
    label: str = Field(..., min_length=1, max_length=64, description="显示标签")
    value: str = Field(..., min_length=1, max_length=128, description="实际值")
    description: str | None = None
    sort: int = Field(default=0, ge=0, description="排序")
    status: int = Field(default=1, ge=0, le=1, description="状态：1正常 0停用")
    is_default: bool = Field(default=False, description="是否默认值")
    css_class: str | None = Field(None, max_length=128, description="样式类")


class DictItemUpdate(BaseModel):
    """更新字典项"""
    label: str | None = Field(None, min_length=1, max_length=64)
    value: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    sort: int | None = Field(None, ge=0)
    status: int | None = Field(None, ge=0, le=1)
    is_default: bool | None = None
    css_class: str | None = Field(None, max_length=128)


class DictItemInfo(BaseModel):
    """字典项信息"""
    id: int
    type_id: int
    label: str
    value: str
    description: str | None
    sort: int
    status: int
    is_default: bool
    css_class: str | None

    class Config:
        from_attributes = True


class DictCodeResult(BaseModel):
    """根据编码获取字典项结果"""
    code: str
    name: str
    items: list[DictItemInfo]


DictTypeWithItems.update_forward_refs()
