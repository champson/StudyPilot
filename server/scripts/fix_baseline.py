import sys

file_path = r"/root/dev/StudyPilot/server/alembic/versions/bd087157109c_initial_baseline.py"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "unique=False" in line and "op.create_index" in line:
        continue
    if "postgresql_using='btree'" in line and "op.drop_index" in line and "weekly_reports" not in line: # drop_index matches are broad, be careful. I'll just skip drop_index lines except what we absolutely need? Wait, downgrade function isn't critical right now. Let's just focus on upgrade.
        # Actually let's just use exact word matching
        pass
        
    if "sa.Column('status', sa.String(length=20), server_default='pending', nullable=False)" in line:
        continue
    if "name='chk_correction_status'" in line:
        continue
    if "name='chk_target_type'" in line:
        continue
    
    # Actually, all non-unique create_index:
    if "op.create_index" in line and "unique=False" in line:
        continue

    # All drop_index that we stripped from create:
    # We will strip all drop_index except unique ones
    # It's okay if downgrade leaves some indexes around since downgrade is rarely used for DB resets of this kind, but to be clean:
    if "op.drop_index" in line and "idx_daily_plan_unique_active" not in line and "idx_error_book_dedup" not in line:
        continue

    # we also want to change nullable=True back to False for corrected_by
    if "sa.Column('corrected_by', sa.Integer(), nullable=True)" in line:
        line = line.replace("nullable=True", "nullable=False")

    new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("done")
