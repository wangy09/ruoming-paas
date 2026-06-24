-- 若茗 PaaS - 补充 AI 模块权限数据
-- 适用于：已初始化数据库，需手动执行此脚本补充权限
-- Author: ruoming
-- Date: 2026-06

-- ── 查找 AI 管理根菜单 ID ─────────────────────────────────────────────
DO $$
DECLARE
    ai_root_id      INTEGER;
    kb_menu_id      INTEGER;
    prompt_menu_id  INTEGER;
    tool_menu_id    INTEGER;
    admin_role_id   INTEGER;
BEGIN
    -- 获取 AI 管理根菜单 ID
    SELECT id INTO ai_root_id FROM sys_permission WHERE code = 'ai' LIMIT 1;
    -- 获取知识库菜单 ID
    SELECT id INTO kb_menu_id FROM sys_permission WHERE code = 'ai:knowledge:menu' LIMIT 1;
    -- 获取 Prompt 菜单 ID
    SELECT id INTO prompt_menu_id FROM sys_permission WHERE code = 'ai:prompt:menu' LIMIT 1;
    -- 获取租户管理员角色 ID
    SELECT id INTO admin_role_id FROM sys_role WHERE code = 'tenant:admin' LIMIT 1;

    -- ── 知识库：补充编辑、删除、删除文档权限 ────────────────────────────
    IF kb_menu_id IS NOT NULL THEN
        -- 编辑知识库
        INSERT INTO sys_permission (parent_id, name, code, perm_type, sort, is_visible, is_system, created_at, updated_at)
        SELECT kb_menu_id, '编辑知识库', 'ai:kb:update', 'button', 2, false, true, NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code = 'ai:kb:update');

        -- 删除知识库
        INSERT INTO sys_permission (parent_id, name, code, perm_type, sort, is_visible, is_system, created_at, updated_at)
        SELECT kb_menu_id, '删除知识库', 'ai:kb:delete', 'button', 3, false, true, NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code = 'ai:kb:delete');

        -- 上传文档（sort 从 2 改为 4，已存在则更新 sort）
        UPDATE sys_permission SET sort = 4 WHERE code = 'ai:kb:upload';

        -- 删除文档
        INSERT INTO sys_permission (parent_id, name, code, perm_type, sort, is_visible, is_system, created_at, updated_at)
        SELECT kb_menu_id, '删除文档', 'ai:kb:doc:delete', 'button', 5, false, true, NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code = 'ai:kb:doc:delete');
    END IF;

    -- ── Prompt：补充删除、版本管理权限 ─────────────────────────────────
    IF prompt_menu_id IS NOT NULL THEN
        -- 删除模板
        INSERT INTO sys_permission (parent_id, name, code, perm_type, sort, is_visible, is_system, created_at, updated_at)
        SELECT prompt_menu_id, '删除模板', 'ai:prompt:delete', 'button', 3, false, true, NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code = 'ai:prompt:delete');

        -- 版本管理
        INSERT INTO sys_permission (parent_id, name, code, perm_type, sort, is_visible, is_system, created_at, updated_at)
        SELECT prompt_menu_id, '版本管理', 'ai:prompt:version', 'button', 4, false, true, NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code = 'ai:prompt:version');
    END IF;

    -- ── 工具管理：新建菜单 + 按钮权限 ──────────────────────────────────
    IF ai_root_id IS NOT NULL THEN
        INSERT INTO sys_permission (parent_id, name, code, perm_type, path, component, icon, sort, is_visible, is_system, created_at, updated_at)
        SELECT ai_root_id, '工具管理', 'ai:tool:menu', 'menu', '/ai/tools', 'ai/tool/index', 'Tools', 260, true, true, NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code = 'ai:tool:menu');

        SELECT id INTO tool_menu_id FROM sys_permission WHERE code = 'ai:tool:menu' LIMIT 1;

        -- 查看工具按钮
        INSERT INTO sys_permission (parent_id, name, code, perm_type, sort, is_visible, is_system, created_at, updated_at)
        SELECT tool_menu_id, '查看工具', 'ai:tool:view', 'button', 1, false, true, NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code = 'ai:tool:view');
    END IF;

    -- ── 给租户管理员角色分配所有新增权限 ───────────────────────────────
    IF admin_role_id IS NOT NULL THEN
        INSERT INTO sys_role_permission (role_id, permission_id)
        SELECT admin_role_id, id
        FROM sys_permission
        WHERE code IN (
            'ai:kb:update', 'ai:kb:delete', 'ai:kb:doc:delete',
            'ai:prompt:delete', 'ai:prompt:version',
            'ai:tool:menu', 'ai:tool:view'
        )
        AND id NOT IN (
            SELECT permission_id FROM sys_role_permission WHERE role_id = admin_role_id
        );
    END IF;

    RAISE NOTICE '✅ AI 权限数据补充完成';
END $$;
