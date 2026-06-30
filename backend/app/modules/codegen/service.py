"""
若茗 PaaS - 代码生成器服务

第一期只生成代码预览，不直接写入文件，避免覆盖用户代码。
"""
from __future__ import annotations

import re
import os
from pathlib import Path
from string import Template

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.codegen.schemas import (
    ColumnInfo,
    GeneratedFile,
    GeneratedWriteResult,
    GeneratePreviewRequest,
    GenerateWriteRequest,
    TableInfo,
)


COMMON_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "tenant_id"}
BACKEND_PREFIX = "backend/"
FRONTEND_PREFIX = "frontend/"


class CodegenService:
    """代码生成器服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_tables(self, keyword: str | None = None) -> list[TableInfo]:
        params = {"keyword": f"%{keyword or ''}%"}
        rows = await self.db.execute(
            text(
                """
                SELECT
                    c.relname AS table_name,
                    obj_description(c.oid, 'pg_class') AS table_comment
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'r'
                  AND n.nspname = 'public'
                  AND c.relname NOT LIKE 'alembic_%'
                  AND (:keyword = '%%' OR c.relname ILIKE :keyword OR COALESCE(obj_description(c.oid, 'pg_class'), '') ILIKE :keyword)
                ORDER BY c.relname
                """
            ),
            params,
        )
        return [TableInfo(**dict(row._mapping)) for row in rows]

    async def get_table(self, table_name: str) -> TableInfo:
        row = await self.db.execute(
            text(
                """
                SELECT
                    c.relname AS table_name,
                    obj_description(c.oid, 'pg_class') AS table_comment
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'r'
                  AND n.nspname = 'public'
                  AND c.relname = :table_name
                """
            ),
            {"table_name": table_name},
        )
        data = row.mappings().first()
        if not data:
            raise NotFoundException("数据表")
        return TableInfo(**dict(data))

    async def list_columns(self, table_name: str) -> list[ColumnInfo]:
        await self.get_table(table_name)
        rows = await self.db.execute(
            text(
                """
                SELECT
                    c.column_name,
                    c.data_type,
                    c.udt_name,
                    c.is_nullable,
                    c.column_default,
                    c.character_maximum_length,
                    c.numeric_precision,
                    c.numeric_scale,
                    col_description(format('%s.%s', c.table_schema, c.table_name)::regclass::oid, c.ordinal_position) AS column_comment,
                    CASE WHEN pk.column_name IS NULL THEN false ELSE true END AS is_primary_key
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT ku.table_name, ku.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku
                      ON tc.constraint_name = ku.constraint_name
                     AND tc.table_schema = ku.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = 'public'
                ) pk ON pk.table_name = c.table_name AND pk.column_name = c.column_name
                WHERE c.table_schema = 'public'
                  AND c.table_name = :table_name
                ORDER BY c.ordinal_position
                """
            ),
            {"table_name": table_name},
        )

        columns: list[ColumnInfo] = []
        for row in rows:
            data = dict(row._mapping)
            data["is_nullable"] = data["is_nullable"] == "YES"
            data["python_type"] = self._python_type(data["data_type"], data["udt_name"])
            data["ts_type"] = self._ts_type(data["data_type"], data["udt_name"])
            data["form_component"] = self._form_component(data["data_type"], data["udt_name"], data["column_name"])
            columns.append(ColumnInfo(**data))
        return columns

    async def preview(self, request: GeneratePreviewRequest) -> dict:
        table, columns, files = await self._build_files(request)
        return {"table": table, "columns": columns, "files": files}

    async def write(self, request: GenerateWriteRequest) -> dict:
        table, columns, files = await self._build_files(request)
        results = [self._write_file(file, overwrite=request.overwrite) for file in files]
        return {"table": table, "columns": columns, "files": files, "results": results}

    async def _build_files(self, request: GeneratePreviewRequest) -> tuple[TableInfo, list[ColumnInfo], list[GeneratedFile]]:
        table = await self.get_table(request.table_name)
        columns = await self.list_columns(request.table_name)

        module_name = request.module_name
        entity_name = request.entity_name or self._pascal_case(module_name)
        page_title = request.page_title or table.table_comment or entity_name
        api_prefix = request.api_prefix or f"/api/v1/{module_name.replace('_', '-')}"

        context = {
            "table_name": table.table_name,
            "table_comment": table.table_comment or page_title,
            "module_name": module_name,
            "entity_name": entity_name,
            "entity_var": self._snake_case(entity_name),
            "page_title": page_title,
            "api_prefix": api_prefix,
            "model_fields": self._render_model_fields(columns),
            "schema_fields": self._render_schema_fields(columns),
            "create_schema_fields": self._render_schema_fields(columns, include_common=False, optional=False),
            "update_schema_fields": self._render_schema_fields(columns, include_common=False, optional=True),
            "table_columns": self._render_vue_table_columns(columns),
            "form_items": self._render_vue_form_items(columns),
            "form_defaults": self._render_vue_form_defaults(columns),
        }

        files = [
            GeneratedFile(path=f"backend/app/modules/{module_name}/__init__.py", language="python", content=""),
            GeneratedFile(path=f"backend/app/modules/{module_name}/models.py", language="python", content=self._tpl_model(context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/schemas.py", language="python", content=self._tpl_schemas(context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/service.py", language="python", content=self._tpl_service(context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/router.py", language="python", content=self._tpl_router(context)),
            GeneratedFile(path=f"frontend/src/api/{module_name}.ts", language="typescript", content=self._tpl_api(context)),
            GeneratedFile(path=f"frontend/src/views/{module_name}/index.vue", language="vue", content=self._tpl_vue(context)),
        ]
        return table, columns, files

    def _write_file(self, file: GeneratedFile, overwrite: bool) -> GeneratedWriteResult:
        target = self._resolve_output_path(file.path)
        if target is None:
            return GeneratedWriteResult(
                path=file.path,
                status="unavailable",
                message="当前后端运行环境无法访问该路径，请配置 CODEGEN_WORKSPACE_ROOT 或挂载仓库根目录",
            )

        if target.exists() and not overwrite:
            return GeneratedWriteResult(
                path=file.path,
                status="skipped",
                message="文件已存在，未开启覆盖",
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_text(file.content, encoding="utf-8")
        return GeneratedWriteResult(
            path=file.path,
            status="overwritten" if existed else "created",
            message="已覆盖" if existed else "已创建",
        )

    @staticmethod
    def _resolve_output_path(logical_path: str) -> Path | None:
        if logical_path.startswith("/") or ".." in Path(logical_path).parts:
            return None

        configured_root = os.getenv("CODEGEN_WORKSPACE_ROOT")
        if configured_root:
            root = Path(configured_root).resolve()
            target = (root / logical_path).resolve()
            if root == target or root in target.parents:
                return target
            return None

        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "backend").is_dir() and (parent / "frontend").is_dir():
                return (parent / logical_path).resolve()

        backend_root = next((parent for parent in current.parents if (parent / "app").is_dir() and (parent / "scripts").is_dir()), None)
        if backend_root and logical_path.startswith(BACKEND_PREFIX):
            return (backend_root / logical_path[len(BACKEND_PREFIX):]).resolve()

        return None

    @staticmethod
    def _python_type(data_type: str, udt_name: str) -> str:
        if data_type in {"bigint", "integer", "smallint"}:
            return "int"
        if data_type in {"numeric", "real", "double precision"}:
            return "float"
        if data_type == "boolean":
            return "bool"
        if data_type.startswith("timestamp") or udt_name in {"date", "time"}:
            return "datetime"
        if data_type in {"json", "jsonb"}:
            return "dict"
        return "str"

    @staticmethod
    def _ts_type(data_type: str, udt_name: str) -> str:
        if data_type in {"bigint", "integer", "smallint", "numeric", "real", "double precision"}:
            return "number"
        if data_type == "boolean":
            return "boolean"
        if data_type in {"json", "jsonb"}:
            return "Record<string, unknown>"
        return "string"

    @staticmethod
    def _form_component(data_type: str, udt_name: str, column_name: str) -> str:
        if data_type == "boolean":
            return "switch"
        if data_type in {"bigint", "integer", "smallint", "numeric", "real", "double precision"}:
            return "number"
        if "content" in column_name or "remark" in column_name or data_type == "text":
            return "textarea"
        if data_type.startswith("timestamp") or udt_name in {"date", "time"}:
            return "datetime"
        return "input"

    @staticmethod
    def _pascal_case(value: str) -> str:
        return "".join(part.capitalize() for part in re.split(r"[_\\-\\s]+", value) if part)

    @staticmethod
    def _snake_case(value: str) -> str:
        value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
        value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
        return value.lower()

    @staticmethod
    def _render_model_fields(columns: list[ColumnInfo]) -> str:
        lines: list[str] = []
        for col in columns:
            if col.column_name in COMMON_FIELDS:
                continue
            nullable = " | None" if col.is_nullable else ""
            comment = col.column_comment or col.column_name
            if col.python_type == "datetime":
                column_type = "DateTime(timezone=True)"
            elif col.python_type == "int":
                column_type = "BigInteger"
            elif col.python_type == "float":
                column_type = "Numeric"
            elif col.python_type == "bool":
                column_type = "Boolean"
            elif col.python_type == "dict":
                column_type = "JSONB"
            elif col.data_type == "text":
                column_type = "Text"
            else:
                length = col.character_maximum_length or 255
                column_type = f"String({length})"
            default_part = ""
            if col.is_nullable:
                default_part = ", default=None"
            elif col.python_type == "bool":
                default_part = ", default=False"
            lines.append(
                f"    {col.column_name}: Mapped[{col.python_type}{nullable}] = "
                f"mapped_column({column_type}, nullable={str(col.is_nullable)}{default_part}, comment=\"{comment}\")"
            )
        return "\n".join(lines) or "    pass"

    @staticmethod
    def _render_schema_fields(columns: list[ColumnInfo], include_common: bool = True, optional: bool = False) -> str:
        lines: list[str] = []
        for col in columns:
            if col.column_name == "is_deleted":
                continue
            if not include_common and col.column_name in COMMON_FIELDS:
                continue
            py_type = col.python_type
            if optional or col.is_nullable:
                py_type = f"{py_type} | None"
                default = " = None"
            else:
                default = ""
            lines.append(f"    {col.column_name}: {py_type}{default}")
        return "\n".join(lines) or "    pass"

    @staticmethod
    def _render_vue_table_columns(columns: list[ColumnInfo]) -> str:
        lines: list[str] = []
        skip = {"is_deleted", "tenant_id", "updated_at"}
        for col in columns:
            if col.column_name in skip:
                continue
            label = col.column_comment or col.column_name
            width = " width=\"170\"" if col.column_name.endswith("_at") else ""
            lines.append(f"      <el-table-column prop=\"{col.column_name}\" label=\"{label}\"{width} show-overflow-tooltip />")
        return "\n".join(lines)

    @staticmethod
    def _render_vue_form_items(columns: list[ColumnInfo]) -> str:
        lines: list[str] = []
        for col in columns:
            if col.column_name in COMMON_FIELDS:
                continue
            label = col.column_comment or col.column_name
            if col.form_component == "textarea":
                control = f"<el-input v-model=\"form.{col.column_name}\" type=\"textarea\" :rows=\"4\" />"
            elif col.form_component == "number":
                control = f"<el-input-number v-model=\"form.{col.column_name}\" style=\"width: 100%\" />"
            elif col.form_component == "switch":
                control = f"<el-switch v-model=\"form.{col.column_name}\" />"
            elif col.form_component == "datetime":
                control = f"<el-date-picker v-model=\"form.{col.column_name}\" type=\"datetime\" value-format=\"YYYY-MM-DD HH:mm:ss\" style=\"width: 100%\" />"
            else:
                control = f"<el-input v-model=\"form.{col.column_name}\" />"
            lines.append(f"        <el-form-item label=\"{label}\">\n          {control}\n        </el-form-item>")
        return "\n".join(lines)

    @staticmethod
    def _render_vue_form_defaults(columns: list[ColumnInfo]) -> str:
        lines: list[str] = []
        for col in columns:
            if col.column_name in COMMON_FIELDS:
                continue
            if col.ts_type == "number":
                default = "undefined"
            elif col.ts_type == "boolean":
                default = "false"
            elif col.ts_type.startswith("Record"):
                default = "{}"
            else:
                default = "''"
            lines.append(f"  {col.column_name}: {default},")
        return "\n".join(lines)

    @staticmethod
    def _template(content: str, context: dict) -> str:
        return Template(content.strip() + "\n").safe_substitute(context)

    def _tpl_model(self, ctx: dict) -> str:
        return self._template(
            '''
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class $entity_name(BaseModel):
    """$table_comment"""

    __tablename__ = "$table_name"

$model_fields
            ''',
            ctx,
        )

    def _tpl_schemas(self, ctx: dict) -> str:
        return self._template(
            '''
from datetime import datetime

from pydantic import BaseModel


class $entity_nameCreate(BaseModel):
$create_schema_fields


class $entity_nameUpdate(BaseModel):
$update_schema_fields


class $entity_nameInfo(BaseModel):
$schema_fields

    class Config:
        from_attributes = True
            ''',
            ctx,
        )

    def _tpl_service(self, ctx: dict) -> str:
        return self._template(
            '''
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.utils.pagination import PageParams
from app.modules.$module_name.models import $entity_name
from app.modules.$module_name.schemas import ${entity_name}Create, ${entity_name}Update


class ${entity_name}Service:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, page_params: PageParams) -> dict:
        conditions = [$entity_name.is_deleted == False]
        total = await self.db.scalar(select(func.count($entity_name.id)).where(*conditions))
        rows = await self.db.execute(
            select($entity_name)
            .where(*conditions)
            .order_by(desc($entity_name.created_at))
            .offset(page_params.offset)
            .limit(page_params.page_size)
        )
        return {
            "items": rows.scalars().all(),
            "total": total or 0,
            "page": page_params.page,
            "page_size": page_params.page_size,
        }

    async def get(self, obj_id: int) -> $entity_name:
        obj = await self.db.scalar(
            select($entity_name).where($entity_name.id == obj_id, $entity_name.is_deleted == False)
        )
        if not obj:
            raise NotFoundException("$page_title")
        return obj

    async def create(self, data: ${entity_name}Create) -> $entity_name:
        obj = $entity_name(**data.model_dump(exclude_unset=True))
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj_id: int, data: ${entity_name}Update) -> $entity_name:
        obj = await self.get(obj_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

    async def delete(self, obj_id: int) -> None:
        obj = await self.get(obj_id)
        obj.is_deleted = True
            ''',
            ctx,
        )

    def _tpl_router(self, ctx: dict) -> str:
        return self._template(
            '''
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.core.response import ApiResponse, ok
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.$module_name.schemas import ${entity_name}Create, ${entity_name}Info, ${entity_name}Update
from app.modules.$module_name.service import ${entity_name}Service
from app.modules.user.models import SysUser

router = APIRouter()


@router.get("", response_model=ApiResponse, summary="$page_title列表")
async def list_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("$module_name:view"))],
    page_params: Annotated[PageParams, Depends()],
) -> ApiResponse:
    svc = ${entity_name}Service(db)
    data = await svc.list(page_params)
    data["items"] = [${entity_name}Info.model_validate(item) for item in data["items"]]
    return ok(data)


@router.post("", response_model=ApiResponse[${entity_name}Info], summary="创建$page_title")
async def create_item(
    body: ${entity_name}Create,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("$module_name:create"))],
) -> ApiResponse[${entity_name}Info]:
    svc = ${entity_name}Service(db)
    obj = await svc.create(body)
    await db.commit()
    await db.refresh(obj)
    return ok(${entity_name}Info.model_validate(obj), message="创建成功")


@router.put("/{obj_id}", response_model=ApiResponse[${entity_name}Info], summary="编辑$page_title")
async def update_item(
    obj_id: int,
    body: ${entity_name}Update,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("$module_name:update"))],
) -> ApiResponse[${entity_name}Info]:
    svc = ${entity_name}Service(db)
    obj = await svc.update(obj_id, body)
    await db.commit()
    await db.refresh(obj)
    return ok(${entity_name}Info.model_validate(obj), message="保存成功")


@router.delete("/{obj_id}", response_model=ApiResponse, summary="删除$page_title")
async def delete_item(
    obj_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("$module_name:delete"))],
) -> ApiResponse:
    svc = ${entity_name}Service(db)
    await svc.delete(obj_id)
    await db.commit()
    return ok(message="删除成功")
            ''',
            ctx,
        )

    def _tpl_api(self, ctx: dict) -> str:
        return self._template(
            '''
import request from '@/utils/request'

export const ${module_name}Api = {
  list: (params: { page?: number; page_size?: number }) =>
    request.get('$api_prefix', { params }),
  create: (data: Record<string, unknown>) =>
    request.post('$api_prefix', data),
  update: (id: number, data: Record<string, unknown>) =>
    request.put(`$api_prefix/$${id}`, data),
  remove: (id: number) =>
    request.delete(`$api_prefix/$${id}`),
}
            ''',
            ctx,
        )

    def _tpl_vue(self, ctx: dict) -> str:
        return self._template(
            '''
<template>
  <div class="page-container">
    <div class="search-bar">
      <el-button type="primary" @click="openDialog()">新增$page_title</el-button>
    </div>
    <el-table v-loading="loading" :data="items" border stripe>
$table_columns
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.page_size"
      :total="total"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="fetchList"
      @size-change="fetchList"
    />

    <el-dialog v-model="dialogVisible" :title="editId ? '编辑$page_title' : '新增$page_title'" width="640px">
      <el-form :model="form" label-width="100px">
$form_items
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ${module_name}Api } from '@/api/$module_name'

const loading = ref(false)
const items = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const query = reactive({ page: 1, page_size: 10 })
const form = reactive({
$form_defaults
})

async function fetchList() {
  loading.value = true
  try {
    const res = await ${module_name}Api.list(query)
    items.value = res.data?.items ?? []
    total.value = res.data?.total ?? 0
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  editId.value = row?.id ?? null
  Object.assign(form, row || {})
  dialogVisible.value = true
}

async function submit() {
  if (editId.value) {
    await ${module_name}Api.update(editId.value, form)
  } else {
    await ${module_name}Api.create(form)
  }
  ElMessage.success('保存成功')
  dialogVisible.value = false
  fetchList()
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm('确定删除该数据？', '提示', { type: 'warning' })
  await ${module_name}Api.remove(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(fetchList)
</script>

<style lang="scss" scoped>
.search-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}
</style>
            ''',
            ctx,
        )
