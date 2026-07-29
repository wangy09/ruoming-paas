"""
若茗 PaaS - 代码生成器服务

使用 Jinja2 模板引擎，模板文件存储在 templates/ 目录下
"""
from __future__ import annotations

import io
import re
import os
import uuid
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.codegen.models import GenTable, GenTableColumn
from app.modules.codegen.schemas import (
    BatchGenerateRequest,
    ColumnConfig,
    ColumnInfo,
    CreateTableRequest,
    GeneratedFile,
    GeneratedWriteResult,
    GeneratePreviewRequest,
    GenerateWriteRequest,
    SaveConfigRequest,
    TableInfo,
)
import structlog

logger = structlog.get_logger(__name__)


COMMON_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "tenant_id"}
BACKEND_PREFIX = "backend/"
FRONTEND_PREFIX = "frontend/"


class CodegenService:
    """代码生成器服务"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self._init_jinja()

    def _init_jinja(self) -> None:
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def _render(self, template_path: str, context: dict) -> str:
        template = self.env.get_template(template_path)
        return template.render(context)

    async def list_tables(self, keyword: str | None = None) -> list[TableInfo]:
        params = {"keyword": f"%{keyword or ''}%"}
        result = await self.db.execute(
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
        tables: list[TableInfo] = []
        for mapping in result.mappings().all():
            data: dict = dict(mapping)
            tables.append(TableInfo(**data))
        return tables

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
            {"table_name": table_name.lower()},
        )
        data = row.mappings().first()
        if not data:
            raise NotFoundException("数据表")
        table_data: dict = dict(data)
        return TableInfo(**table_data)

    async def list_columns(self, table_name: str) -> list[ColumnInfo]:
        try:
            await self.get_table(table_name)
        except NotFoundException:
            return []
        result = await self.db.execute(
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
        for mapping in result.mappings().all():
            data: dict = dict(mapping)
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
        temp_dir = None
        committed_files = []

        try:
            temp_dir = self._create_temp_dir()
            write_results = []
            for file in files:
                result = self._write_file_to_temp(file, temp_dir, overwrite=request.overwrite)
                write_results.append(result)
                if result.status in ("created", "overwritten"):
                    committed_files.append((file.path, result))

            for file_path, result in committed_files:
                self._commit_file(temp_dir, file_path)

            return {"table": table, "columns": columns, "files": files, "results": write_results}
        except Exception as e:
            if committed_files:
                self._rollback_files(committed_files)
            raise
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def _build_files(self, request: GeneratePreviewRequest) -> tuple[TableInfo, list[ColumnInfo], list[GeneratedFile]]:
        from sqlalchemy import text
        check_table = await self.db.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :name)"),
            {"name": request.table_name.lower()}
        )
        table_exists = check_table.scalar_one()

        if table_exists:
            table = await self.get_table(request.table_name)
            columns = await self.list_columns(request.table_name)
        else:
            table = TableInfo(
                table_name=request.table_name,
                table_comment="",
            )
            columns: list[ColumnInfo] = []
            if request.column_configs:
                for col in request.column_configs:
                    data_type = getattr(col, "data_type", "VARCHAR")
                    udt_name = getattr(col, "udt_name", data_type.lower())
                    columns.append(ColumnInfo(
                        column_name=col.column_name,
                        data_type=data_type,
                        udt_name=udt_name,
                        is_nullable=getattr(col, "is_nullable", True),
                        column_default=getattr(col, "column_default", None),
                        character_maximum_length=getattr(col, "data_length", None),
                        numeric_precision=getattr(col, "data_length", None),
                        numeric_scale=getattr(col, "data_scale", None),
                        column_comment=getattr(col, "column_comment", None),
                        is_primary_key=getattr(col, "is_primary_key", False),
                        python_type=self._python_type(data_type, udt_name),
                        ts_type=self._ts_type(data_type, udt_name),
                        form_component=col.form_component,
                    ))

        sub_tables_info = []
        if request.sub_tables:
            for sub_table_config in request.sub_tables:
                sub_columns: list[ColumnInfo] = []
                for col in sub_table_config.columns:
                    data_type = getattr(col, "data_type", "VARCHAR")
                    udt_name = getattr(col, "udt_name", data_type.lower())
                    sub_columns.append(ColumnInfo(
                        column_name=col.column_name,
                        data_type=data_type,
                        udt_name=udt_name,
                        is_nullable=getattr(col, "is_nullable", True),
                        column_default=getattr(col, "column_default", None),
                        character_maximum_length=getattr(col, "data_length", None),
                        numeric_precision=getattr(col, "data_length", None),
                        numeric_scale=getattr(col, "data_scale", None),
                        column_comment=getattr(col, "column_comment", None),
                        is_primary_key=getattr(col, "is_primary_key", False),
                        python_type=self._python_type(data_type, udt_name),
                        ts_type=self._ts_type(data_type, udt_name),
                        form_component=col.form_component,
                        foreign_key_table=getattr(col, "foreign_key_table", None),
                    ))
                sub_tables_info.append({
                    "table_name": sub_table_config.table_name,
                    "table_comment": sub_table_config.table_comment or "",
                    "parent_key": sub_table_config.parent_key,
                    "entity_name": sub_table_config.entity_name or self._pascal_case(sub_table_config.table_name),
                    "columns": sub_columns,
                })

        module_name = request.module_name
        entity_name = request.entity_name or self._pascal_case(module_name)
        page_title = request.page_title or table.table_comment or entity_name
        api_prefix = request.api_prefix or f"/api/v1/{module_name.replace('_', '-')}"
        route_path = f"/{module_name.replace('_', '-')}"

        context = self._build_context(
            table=table,
            columns=columns,
            module_name=module_name,
            entity_name=entity_name,
            page_title=page_title,
            api_prefix=api_prefix,
            route_path=route_path,
            sub_tables=sub_tables_info,
            template_type=request.template_type,
        )

        files = [
            GeneratedFile(path=f"backend/app/modules/{module_name}/__init__.py", language="python", content=""),
            GeneratedFile(path=f"backend/app/modules/{module_name}/models.py", language="python", content=self._render("backend/model.py.tpl", context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/schemas.py", language="python", content=self._render("backend/schemas.py.tpl", context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/repository.py", language="python", content=self._render("backend/repository.py.tpl", context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/service.py", language="python", content=self._render("backend/service.py.tpl", context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/router.py", language="python", content=self._render("backend/router.py.tpl", context)),
            GeneratedFile(path=f"backend/migrations/versions/{context['migration_id']}_add_{module_name}_table.py", language="python", content=self._render("backend/migration.py.tpl", context)),
            GeneratedFile(path=f"frontend/src/api/{module_name}.ts", language="typescript", content=self._render("frontend/api.ts.tpl", context)),
            GeneratedFile(path=f"frontend/src/views/{module_name}/index.vue", language="vue", content=self._render("frontend/index.vue.tpl", context)),
            GeneratedFile(path=f"frontend/src/views/{module_name}/components/FormDialog.vue", language="vue", content=self._render("frontend/form-dialog.vue.tpl", context)),
        ]
        return table, columns, files

    def _build_context(self, table: TableInfo, columns: list[ColumnInfo], module_name: str, entity_name: str, page_title: str, api_prefix: str, route_path: str, sub_tables: list | None = None, template_type: str = "single") -> dict:
        model_fields = self._render_model_fields(columns)
        create_schema_fields = self._render_schema_fields(columns, include_common=False, optional=False)
        update_schema_fields = self._render_schema_fields(columns, include_common=False, optional=True)
        schema_fields = self._render_schema_fields(columns, include_common=True, optional=False)
        table_columns = self._render_vue_table_columns(columns)
        form_items = self._render_vue_form_items(columns)
        form_defaults = self._render_vue_form_defaults(columns)
        ts_type_fields = self._render_ts_type_fields(columns)
        migration_fields = self._render_migration_fields(columns)

        sqlalchemy_imports = self._collect_sqlalchemy_imports(columns)
        searchable_fields = self._collect_searchable_fields(columns)
        has_jsonb = any(col.data_type in {"json", "jsonb"} for col in columns)
        has_search_fields = len(searchable_fields) > 0

        sub_tables_context = []
        if sub_tables:
            for st in sub_tables:
                st_model_fields = self._render_model_fields(st["columns"])
                st_create_fields = self._render_schema_fields(st["columns"], include_common=False, optional=False)
                st_update_fields = self._render_schema_fields(st["columns"], include_common=False, optional=True)
                st_schema_fields = self._render_schema_fields(st["columns"], include_common=True, optional=False)
                st_table_columns = self._render_vue_table_columns(st["columns"])
                st_form_items = self._render_vue_form_items(st["columns"])
                st_form_defaults = self._render_vue_form_defaults(st["columns"])
                st_ts_fields = self._render_ts_type_fields(st["columns"])
                st_migration_fields = self._render_migration_fields(st["columns"])
                sub_tables_context.append({
                    "table_name": st["table_name"],
                    "table_comment": st["table_comment"],
                    "parent_key": st["parent_key"],
                    "entity_name": st["entity_name"],
                    "entity_var": self._snake_case(st["entity_name"]),
                    "columns": st["columns"],
                    "model_fields": st_model_fields,
                    "create_schema_fields": st_create_fields,
                    "update_schema_fields": st_update_fields,
                    "schema_fields": st_schema_fields,
                    "table_columns": st_table_columns,
                    "form_items": st_form_items,
                    "form_defaults": st_form_defaults,
                    "ts_type_fields": st_ts_fields,
                    "migration_fields": st_migration_fields,
                })

        return {
            "table_name": table.table_name,
            "table_comment": table.table_comment or page_title,
            "module_name": module_name,
            "entity_name": entity_name,
            "entity_var": self._snake_case(entity_name),
            "page_title": page_title,
            "api_prefix": api_prefix,
            "route_path": route_path,
            "model_fields": model_fields,
            "schema_fields": schema_fields,
            "create_schema_fields": create_schema_fields,
            "update_schema_fields": update_schema_fields,
            "table_columns": table_columns,
            "form_items": form_items,
            "form_defaults": form_defaults,
            "ts_type_fields": ts_type_fields,
            "migration_fields": migration_fields,
            "sqlalchemy_imports": sqlalchemy_imports,
            "searchable_fields": searchable_fields,
            "has_jsonb": has_jsonb,
            "has_search_fields": has_search_fields,
            "sub_tables": sub_tables_context,
            "has_sub_tables": len(sub_tables_context) > 0,
            "template_type": template_type,
            "is_single_table": template_type == "single",
            "is_master_detail": template_type == "master_detail",
            "is_tree": template_type == "tree",
            "migration_id": self._generate_migration_id(),
            "create_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

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

    def _create_temp_dir(self) -> Path:
        import tempfile
        temp_dir = Path(tempfile.mkdtemp(prefix="codegen_"))
        return temp_dir

    def _write_file_to_temp(self, file: GeneratedFile, temp_dir: Path, overwrite: bool) -> GeneratedWriteResult:
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

        temp_path = temp_dir / file.path
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(file.content, encoding="utf-8")
        return GeneratedWriteResult(
            path=file.path,
            status="overwritten" if target.exists() else "created",
            message="已覆盖" if target.exists() else "已创建",
        )

    def _commit_file(self, temp_dir: Path, file_path: str) -> None:
        target = self._resolve_output_path(file_path)
        if target is None:
            return
        temp_path = temp_dir / file_path
        if temp_path.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp_path), str(target))

    def _rollback_files(self, committed_files: list[tuple[str, GeneratedWriteResult]]) -> None:
        for file_path, result in committed_files:
            if result.status == "created":
                target = self._resolve_output_path(file_path)
                if target and target.exists():
                    try:
                        target.unlink()
                        self._remove_empty_parent(target.parent)
                    except Exception as e:
                        logger.debug("codegen_file_cleanup_failed", error=str(e))
            elif result.status == "overwritten":
                pass

    def _remove_empty_parent(self, directory: Path) -> None:
        try:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
                self._remove_empty_parent(directory.parent)
        except Exception as e:
            logger.debug("codegen_dir_cleanup_failed", error=str(e))

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
        if data_type.startswith("timestamp") or udt_name in {"date", "time"}:
            return "string"
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
    def _generate_migration_id() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _collect_sqlalchemy_imports(columns: list[ColumnInfo]) -> list[str]:
        imports = {"BigInteger", "Boolean", "DateTime", "Numeric", "String", "Text"}
        for col in columns:
            if col.data_type == "text":
                imports.add("Text")
            elif col.data_type in {"bigint", "integer", "smallint"}:
                imports.add("BigInteger")
            elif col.data_type in {"numeric", "real", "double precision"}:
                imports.add("Numeric")
            elif col.data_type == "boolean":
                imports.add("Boolean")
            elif col.data_type.startswith("timestamp"):
                imports.add("DateTime")
            elif col.data_type in {"json", "jsonb"}:
                pass
            else:
                imports.add("String")
        return sorted(imports)

    @staticmethod
    def _collect_searchable_fields(columns: list[ColumnInfo]) -> list[str]:
        searchable = []
        for col in columns:
            if col.column_name in COMMON_FIELDS:
                continue
            if col.python_type in {"str"} or col.data_type == "text":
                searchable.append(col.column_name)
        return searchable

    @staticmethod
    def _render_model_fields(columns: list[ColumnInfo]) -> list[str]:
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
                f"{col.column_name}: Mapped[{col.python_type}{nullable}] = "
                f"mapped_column({column_type}, nullable={str(col.is_nullable)}{default_part}, comment=\"{comment}\")"
            )
        return lines or ["    pass"]

    @staticmethod
    def _render_schema_fields(columns: list[ColumnInfo], include_common: bool = True, optional: bool = False) -> list[str]:
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
            lines.append(f"{col.column_name}: {py_type}{default}")
        return lines or ["    pass"]

    @staticmethod
    def _render_vue_table_columns(columns: list[ColumnInfo]) -> list[dict]:
        result: list[dict] = []
        skip = {"is_deleted", "tenant_id", "updated_at"}
        for col in columns:
            if col.column_name in skip:
                continue
            label = col.column_comment or col.column_name
            width = ' width="170"' if col.column_name.endswith("_at") else ""
            result.append({
                "prop": col.column_name,
                "label": label,
                "width": width,
            })
        return result

    @staticmethod
    def _render_vue_form_items(columns: list[ColumnInfo]) -> list[dict]:
        result: list[dict] = []
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
            result.append({
                "label": label,
                "control": control,
            })
        return result

    @staticmethod
    def _render_vue_form_defaults(columns: list[ColumnInfo]) -> list[dict]:
        result: list[dict] = []
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
            result.append({
                "name": col.column_name,
                "default": default,
            })
        return result

    @staticmethod
    def _render_ts_type_fields(columns: list[ColumnInfo]) -> list[dict]:
        result: list[dict] = []
        for col in columns:
            if col.column_name in COMMON_FIELDS:
                continue
            result.append({
                "name": col.column_name,
                "type": col.ts_type,
            })
        return result

    @staticmethod
    def _render_migration_fields(columns: list[ColumnInfo]) -> list[dict]:
        result: list[dict] = []
        for col in columns:
            if col.column_name in COMMON_FIELDS:
                continue
            comment = col.column_comment or col.column_name
            if col.data_type in {"bigint", "integer", "smallint"}:
                sa_type = "sa.BigInteger()"
            elif col.data_type in {"numeric", "real", "double precision"}:
                sa_type = "sa.Numeric()"
            elif col.data_type == "boolean":
                sa_type = "sa.Boolean()"
            elif col.data_type.startswith("timestamp"):
                sa_type = "sa.DateTime(timezone=True)"
            elif col.data_type in {"json", "jsonb"}:
                sa_type = "postgresql.JSONB()"
            elif col.data_type == "text":
                sa_type = "sa.Text()"
            else:
                length = col.character_maximum_length or 255
                sa_type = f"sa.String({length})"
            default = None
            if col.column_default:
                if col.column_default.lower() in {"true", "false"}:
                    default = col.column_default.lower()
                elif col.column_default.isdigit():
                    default = col.column_default
            result.append({
                "name": col.column_name,
                "type": sa_type,
                "nullable": col.is_nullable,
                "default": default,
                "comment": comment,
            })
        return result

    async def save_config(self, request: SaveConfigRequest, created_by: int | None = None) -> GenTable:
        query = select(GenTable).where(GenTable.table_name == request.table_name, GenTable.is_deleted == False)
        if self.tenant_id is not None:
            query = query.where(GenTable.tenant_id == self.tenant_id)
        existing = await self.db.execute(query)
        existing = existing.scalar_one_or_none()

        if existing:
            existing.table_comment = request.table_comment
            existing.module_name = request.module_name
            existing.entity_name = request.entity_name
            existing.page_title = request.page_title
            existing.api_prefix = request.api_prefix
            existing.author = request.author
            existing.remark = request.remark
            table = existing
        else:
            table = GenTable(
                table_name=request.table_name,
                table_comment=request.table_comment,
                module_name=request.module_name,
                entity_name=request.entity_name,
                page_title=request.page_title,
                api_prefix=request.api_prefix,
                author=request.author,
                remark=request.remark,
                created_by=created_by,
                tenant_id=self.tenant_id,
            )
            self.db.add(table)
        await self.db.flush()

        await self.db.execute(
            delete(GenTableColumn).where(GenTableColumn.table_id == table.id)
        )

        for idx, col_config in enumerate(request.columns):
            column_info = None
            try:
                column_info = await self._get_column_info(request.table_name, col_config.column_name)
            except NotFoundException:
                pass

            column = GenTableColumn(
                table_id=table.id,
                column_name=col_config.column_name,
                column_comment=column_info.column_comment if column_info else None,
                data_type=column_info.data_type if column_info else "",
                udt_name=column_info.udt_name if column_info else "",
                is_nullable=column_info.is_nullable if column_info else True,
                is_primary_key=column_info.is_primary_key if column_info else False,
                is_list=col_config.is_list,
                is_form=col_config.is_form,
                is_search=col_config.is_search,
                is_required=col_config.is_required,
                form_component=col_config.form_component,
                dict_type=col_config.dict_type,
                sort=col_config.sort or idx,
            )
            self.db.add(column)

        await self.db.commit()
        return table

    async def _get_column_info(self, table_name: str, column_name: str) -> ColumnInfo | None:
        columns = await self.list_columns(table_name)
        return next((col for col in columns if col.column_name == column_name), None)

    async def get_config(self, config_id: int) -> dict:
        table = await self.db.execute(
            select(GenTable).where(GenTable.id == config_id, GenTable.is_deleted == False)
        )
        table = table.scalar_one_or_none()
        if not table:
            raise NotFoundException("代码生成配置")

        from sqlalchemy import text
        check_table = await self.db.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :name)"),
            {"name": table.table_name.lower()}
        )
        table_exists = check_table.scalar_one()

        columns = await self.db.execute(
            select(GenTableColumn).where(GenTableColumn.table_id == table.id, GenTableColumn.is_deleted == False).order_by(GenTableColumn.sort)
        )
        columns = columns.scalars().all()

        return {
            "id": table.id,
            "table_name": table.table_name,
            "table_comment": table.table_comment,
            "module_name": table.module_name,
            "entity_name": table.entity_name,
            "page_title": table.page_title,
            "api_prefix": table.api_prefix,
            "author": table.author,
            "status": table.status,
            "remark": table.remark,
            "columns": [self._column_to_dict(col) for col in columns],
            "table_exists": table_exists,
            "created_at": table.created_at.isoformat() if table.created_at else None,
            "updated_at": table.updated_at.isoformat() if table.updated_at else None,
        }

    async def list_configs(self, page: int = 1, page_size: int = 20, keyword: str | None = None) -> dict:
        from sqlalchemy import func, text

        query = select(GenTable).where(GenTable.is_deleted == False)
        if self.tenant_id is not None:
            query = query.where(GenTable.tenant_id == self.tenant_id)
        if keyword:
            query = query.where(
                GenTable.table_name.ilike(f"%{keyword}%")
                | GenTable.table_comment.ilike(f"%{keyword}%")
                | GenTable.module_name.ilike(f"%{keyword}%")
            )
        query = query.order_by(GenTable.created_at.desc())

        count_query = select(func.count()).select_from(query.subquery())
        count = await self.db.execute(count_query)
        total = count.scalar_one()

        query = query.offset((page - 1) * page_size).limit(page_size)
        tables = await self.db.execute(query)
        tables = tables.scalars().all()

        if not tables:
            return {"total": total, "items": []}

        # 批量查询：一次获取所有表格列信息（消除 N+1）
        table_ids = [t.id for t in tables]
        columns_query = select(GenTableColumn).where(
            GenTableColumn.table_id.in_(table_ids),
            GenTableColumn.is_deleted == False,  # noqa: E712
        ).order_by(GenTableColumn.table_id, GenTableColumn.sort)
        all_columns = await self.db.execute(columns_query)
        all_columns_map: dict[int, list] = {}
        for col in all_columns.scalars().all():
            all_columns_map.setdefault(col.table_id, []).append(col)

        # 批量查询：一次获取所有表名的存在性（消除 N+1）
        table_names = [t.table_name.lower() for t in tables]
        placeholders = ", ".join([f":t{i}" for i in range(len(table_names))])
        exists_sql = text(
            f"SELECT table_name FROM information_schema.tables WHERE table_name IN ({placeholders})"
        )
        params = {f"t{i}": name for i, name in enumerate(table_names)}
        exists_result = await self.db.execute(exists_sql, params)
        existing_names = {row[0] for row in exists_result.all()}

        items = []
        for table in tables:
            columns = all_columns_map.get(table.id, [])
            items.append({
                "id": table.id,
                "table_name": table.table_name,
                "table_comment": table.table_comment,
                "module_name": table.module_name,
                "entity_name": table.entity_name,
                "page_title": table.page_title,
                "api_prefix": table.api_prefix,
                "author": table.author,
                "status": table.status,
                "remark": table.remark,
                "columns": [self._column_to_dict(col) for col in columns],
                "table_exists": table.table_name.lower() in existing_names,
                "created_at": table.created_at.isoformat() if table.created_at else None,
                "updated_at": table.updated_at.isoformat() if table.updated_at else None,
            })

        return {"total": total, "items": items}

    async def delete_config(self, config_id: int) -> None:
        table = await self.db.execute(
            select(GenTable).where(GenTable.id == config_id, GenTable.is_deleted == False)
        )
        table = table.scalar_one_or_none()
        if not table:
            raise NotFoundException("代码生成配置")

        table.is_deleted = True
        await self.db.execute(
            update(GenTableColumn).where(GenTableColumn.table_id == config_id).values(is_deleted=True)
        )
        await self.db.commit()

    async def generate_from_config(self, config_id: int, overwrite: bool = False) -> dict:
        config = await self.get_config(config_id)

        from sqlalchemy import text
        check_table = await self.db.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :name)"),
            {"name": config["table_name"].lower()}
        )
        table_exists = check_table.scalar_one()

        if table_exists:
            request = GenerateWriteRequest(
                table_name=config["table_name"],
                module_name=config["module_name"],
                entity_name=config["entity_name"],
                page_title=config["page_title"],
                api_prefix=config["api_prefix"],
                column_configs=[ColumnConfig(**col) for col in config["columns"]],
                overwrite=overwrite,
            )
            return await self.write(request)
        else:
            return await self._generate_from_config_only(config_id, overwrite)

    async def _generate_from_config_only(self, config_id: int, overwrite: bool = False) -> dict:
        config = await self.get_config(config_id)

        table = TableInfo(
            table_name=config["table_name"],
            table_comment=config["table_comment"],
        )

        columns: list[ColumnInfo] = []
        for col in config["columns"]:
            columns.append(ColumnInfo(
                column_name=col["column_name"],
                data_type=col.get("data_type", "VARCHAR"),
                udt_name=col.get("udt_name", col.get("data_type", "varchar").lower()),
                is_nullable=col.get("is_nullable", True),
                column_default=col.get("column_default"),
                character_maximum_length=col.get("data_length"),
                numeric_precision=col.get("data_length"),
                numeric_scale=col.get("data_scale"),
                column_comment=col.get("column_comment"),
                is_primary_key=col.get("is_primary_key", False),
                python_type=self._python_type(col.get("data_type", "VARCHAR"), col.get("udt_name", "varchar")),
                ts_type=self._ts_type(col.get("data_type", "VARCHAR"), col.get("udt_name", "varchar")),
                form_component=col.get("form_component", "input"),
            ))

        module_name = config["module_name"]
        entity_name = config["entity_name"]
        page_title = config["page_title"] or config["table_comment"] or entity_name
        api_prefix = config["api_prefix"] or f"/api/v1/{module_name.replace('_', '-')}"
        route_path = f"/{module_name.replace('_', '-')}"

        context = self._build_context(
            table=table,
            columns=columns,
            module_name=module_name,
            entity_name=entity_name,
            page_title=page_title,
            api_prefix=api_prefix,
            route_path=route_path,
        )

        files = [
            GeneratedFile(path=f"backend/app/modules/{module_name}/__init__.py", language="python", content=""),
            GeneratedFile(path=f"backend/app/modules/{module_name}/models.py", language="python", content=self._render("backend/model.py.tpl", context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/schemas.py", language="python", content=self._render("backend/schemas.py.tpl", context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/repository.py", language="python", content=self._render("backend/repository.py.tpl", context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/service.py", language="python", content=self._render("backend/service.py.tpl", context)),
            GeneratedFile(path=f"backend/app/modules/{module_name}/router.py", language="python", content=self._render("backend/router.py.tpl", context)),
            GeneratedFile(path=f"backend/migrations/versions/{context['migration_id']}_add_{module_name}_table.py", language="python", content=self._render("backend/migration.py.tpl", context)),
            GeneratedFile(path=f"frontend/src/api/{module_name}.ts", language="typescript", content=self._render("frontend/api.ts.tpl", context)),
            GeneratedFile(path=f"frontend/src/views/{module_name}/index.vue", language="vue", content=self._render("frontend/index.vue.tpl", context)),
            GeneratedFile(path=f"frontend/src/views/{module_name}/components/FormDialog.vue", language="vue", content=self._render("frontend/form-dialog.vue.tpl", context)),
            GeneratedFile(path=f"frontend/src/router/{module_name}.ts", language="typescript", content=self._render("frontend/route.ts.tpl", context)),
        ]

        results = [self._write_file(file, overwrite=overwrite) for file in files]
        return {"table": table, "columns": columns, "files": files, "results": results}

    async def batch_generate(self, request: BatchGenerateRequest) -> list[dict]:
        results = []
        for config_id in request.config_ids:
            result = await self.generate_from_config(config_id, request.overwrite)
            results.append(result)
        return results

    async def generate_zip(self, config_id: int) -> bytes:
        config = await self.get_config(config_id)
        request = GeneratePreviewRequest(
            table_name=config["table_name"],
            module_name=config["module_name"],
            entity_name=config["entity_name"],
            page_title=config["page_title"],
            api_prefix=config["api_prefix"],
            column_configs=[ColumnConfig(**col) for col in config["columns"]],
        )
        preview = await self.preview(request)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in preview["files"]:
                if file.content:
                    zf.writestr(file.path, file.content)

        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def _column_to_dict(col: GenTableColumn) -> dict:
        return {
            "id": col.id,
            "column_name": col.column_name,
            "column_comment": col.column_comment,
            "data_type": col.data_type,
            "udt_name": col.udt_name,
            "is_nullable": col.is_nullable,
            "is_primary_key": col.is_primary_key,
            "is_list": col.is_list,
            "is_form": col.is_form,
            "is_search": col.is_search,
            "is_required": col.is_required,
            "form_component": col.form_component,
            "dict_type": col.dict_type,
            "sort": col.sort,
            "python_type": CodegenService._python_type(col.data_type, col.udt_name),
            "ts_type": CodegenService._ts_type(col.data_type, col.udt_name),
        }

    @staticmethod
    def _validate_table_name(table_name: str) -> None:
        if not re.match(r'^[a-z][a-z0-9_]*$', table_name):
            raise ValueError("表名只能包含小写字母、数字和下划线，且必须以字母开头")
        if len(table_name) > 63:
            raise ValueError("表名长度不能超过63个字符")

    @staticmethod
    def _validate_column_name(column_name: str) -> None:
        if not re.match(r'^[a-z][a-z0-9_]*$', column_name):
            raise ValueError("字段名只能包含小写字母、数字和下划线，且必须以字母开头")
        if len(column_name) > 63:
            raise ValueError("字段名长度不能超过63个字符")

    @staticmethod
    def _get_supported_field_types() -> list[dict]:
        return [
            {"type_name": "VARCHAR", "display_name": "字符串", "default_length": 128, "supports_length": True, "supports_scale": False, "default_nullable": True},
            {"type_name": "TEXT", "display_name": "文本", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
            {"type_name": "BIGINT", "display_name": "长整型", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
            {"type_name": "INT", "display_name": "整型", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
            {"type_name": "SMALLINT", "display_name": "短整型", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
            {"type_name": "DECIMAL", "display_name": "小数", "default_length": 18, "supports_length": True, "supports_scale": True, "default_nullable": True},
            {"type_name": "FLOAT", "display_name": "浮点", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
            {"type_name": "BOOLEAN", "display_name": "布尔", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
            {"type_name": "DATE", "display_name": "日期", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
            {"type_name": "TIME", "display_name": "时间", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
            {"type_name": "TIMESTAMP", "display_name": "日期时间", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
            {"type_name": "JSONB", "display_name": "JSON", "default_length": None, "supports_length": False, "supports_scale": False, "default_nullable": True},
        ]

    async def create_table_from_config(self, request: "CreateTableRequest", created_by: int | None = None) -> dict:
        from sqlalchemy import text

        query = select(GenTable).where(GenTable.table_name == request.table_name, GenTable.is_deleted == False)
        if self.tenant_id is not None:
            query = query.where(GenTable.tenant_id == self.tenant_id)
        existing = await self.db.execute(query)
        existing = existing.scalar_one_or_none()
        if existing:
            raise ValueError(f"表 '{request.table_name}' 的配置已存在")

        if request.create_db_table:
            check_table = await self.db.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :name)"),
                {"name": request.table_name.lower()}
            )
            if check_table.scalar_one():
                raise ValueError(f"数据库表 '{request.table_name}' 已存在")

            self._validate_table_name(request.table_name)

            field_types = {ft["type_name"]: ft for ft in self._get_supported_field_types()}

            columns_sql = []
            params = {}
            param_counter = 1

            for field in request.fields:
                self._validate_column_name(field.column_name)

                if field.data_type not in field_types:
                    raise ValueError(f"不支持的数据类型: {field.data_type}")
                col_sql = f'"{field.column_name}" {field.data_type}'
                type_info = field_types[field.data_type]
                supports_length = type_info.get("supports_length", True)
                supports_scale = type_info.get("supports_scale", False)
                if field.data_length and supports_length:
                    if field.data_scale is not None and supports_scale:
                        col_sql += f"({field.data_length}, {field.data_scale})"
                    else:
                        col_sql += f"({field.data_length})"
                if not field.is_nullable:
                    col_sql += " NOT NULL"
                if field.column_default:
                    default_val = field.column_default.strip()
                    if default_val.lower() in ("true", "false", "now()", "current_timestamp", "current_date", "current_time"):
                        col_sql += f" DEFAULT {default_val}"
                    elif default_val.isdigit():
                        col_sql += f" DEFAULT {default_val}"
                    elif (default_val.startswith("'") and default_val.endswith("'")) or (default_val.startswith('"') and default_val.endswith('"')):
                        param_name = f"default_{param_counter}"
                        params[param_name] = default_val[1:-1]
                        col_sql += f" DEFAULT :{param_name}"
                        param_counter += 1
                    else:
                        raise ValueError(f"不支持的默认值格式: {field.column_default}")
                if field.column_comment:
                    param_name = f"comment_{param_counter}"
                    params[param_name] = field.column_comment
                    col_sql += f" COMMENT :{param_name}"
                    param_counter += 1
                columns_sql.append(col_sql)

            default_columns = [
                '"id" BIGSERIAL PRIMARY KEY',
                '"created_at" TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
                '"updated_at" TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
                '"is_deleted" BOOLEAN DEFAULT FALSE',
                '"tenant_id" BIGINT',
                '"created_by" BIGINT',
                '"updated_by" BIGINT',
            ]

            all_columns = columns_sql + default_columns
            foreign_keys = []

            for field in request.fields:
                if field.foreign_key_table:
                    fk_name = f"fk_{request.table_name}_{field.column_name}"
                    foreign_keys.append(f"CONSTRAINT {fk_name} FOREIGN KEY ({field.column_name}) REFERENCES \"{field.foreign_key_table}\"(id) ON DELETE CASCADE")

            all_definitions = all_columns + foreign_keys

            create_sql = f"""
                CREATE TABLE "{request.table_name}" (
                    {', '.join(all_definitions)}
                )
            """

            if request.table_comment:
                param_name = f"table_comment_{param_counter}"
                params[param_name] = request.table_comment
                create_sql += f" COMMENT = :{param_name}"

            await self.db.execute(text(create_sql), params)

        entity_name = request.entity_name or self._pascal_case(request.table_name)
        api_prefix = request.api_prefix or f"/api/v1/{request.table_name}"

        table = GenTable(
            table_name=request.table_name,
            table_comment=request.table_comment,
            module_name=request.module_name,
            entity_name=entity_name,
            page_title=request.page_title,
            api_prefix=api_prefix,
            author=request.author,
            remark=request.remark,
            created_by=created_by,
            tenant_id=self.tenant_id,
        )
        self.db.add(table)
        await self.db.flush()

        for idx, field in enumerate(request.fields):
            column = GenTableColumn(
                table_id=table.id,
                column_name=field.column_name,
                column_comment=field.column_comment,
                data_type=field.data_type,
                udt_name=field.data_type.lower(),
                is_nullable=field.is_nullable,
                is_primary_key=field.is_primary_key,
                is_list=field.is_list,
                is_form=field.is_form,
                is_search=field.is_search,
                is_required=field.is_required,
                form_component=field.form_component,
                dict_type=field.dict_type,
                foreign_key_table=field.foreign_key_table,
                sort=field.sort or idx,
            )
            self.db.add(column)

        if request.sub_tables:
            for sub_table in request.sub_tables:
                sub_entity_name = sub_table.entity_name or self._pascal_case(sub_table.table_name)
                sub_api_prefix = f"/api/v1/{sub_table.table_name.replace('_', '-')}"
                
                sub_table_record = GenTable(
                    table_name=sub_table.table_name,
                    table_comment=sub_table.table_comment,
                    module_name=request.module_name,
                    entity_name=sub_entity_name,
                    page_title=sub_table.table_comment or sub_entity_name,
                    api_prefix=sub_api_prefix,
                    author=request.author,
                    remark=sub_table.table_comment or "子表",
                    created_by=created_by,
                    tenant_id=self.tenant_id,
                )
                self.db.add(sub_table_record)
                await self.db.flush()

                for idx, field in enumerate(sub_table.columns):
                    sub_column = GenTableColumn(
                        table_id=sub_table_record.id,
                        column_name=field.column_name,
                        column_comment=field.column_comment,
                        data_type=field.data_type,
                        udt_name=field.data_type.lower(),
                        is_nullable=field.is_nullable,
                        is_primary_key=field.is_primary_key,
                        is_list=field.is_list,
                        is_form=field.is_form,
                        is_search=field.is_search,
                        is_required=field.is_required,
                        form_component=field.form_component,
                        dict_type=field.dict_type,
                        foreign_key_table=field.foreign_key_table,
                        sort=field.sort or idx,
                    )
                    self.db.add(sub_column)

        await self.db.commit()

        return await self.generate_from_config(table.id)