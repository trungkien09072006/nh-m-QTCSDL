:on error exit

:r $(Root)\01_schema\01_create_database.sql
:r $(Root)\01_schema\02_create_tables.sql
:r $(Root)\01_schema\03_seed_roles.sql
:r $(Root)\02_data_views\01_create_views.sql
:r $(Root)\03_programmability\01_triggers.sql
:r $(Root)\03_programmability\02_stored_procedures.sql
:r $(Root)\05_admin_tuning\01_performance_indexes.sql
:r $(Root)\05_admin_tuning\02_backup_restore.sql
