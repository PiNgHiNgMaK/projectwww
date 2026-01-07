from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "academic_secret_key"

def load_data(filename):
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=4)
        return []
    if os.path.getsize(filename) == 0: return []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def load_config(filename, default=None):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return default

def is_within_timeline():
    timeline = load_config('timeline.json')
    if not timeline: return True # Default to open if no config
    start = datetime.strptime(timeline['start_date'], "%d/%m/%Y")
    end = datetime.strptime(timeline['end_date'], "%d/%m/%Y")
    now = datetime.now()
    return start <= now <= end

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def calculate_work_score(work_type, work_level, role):
    """
    คำนวณคะแนน (Score) และค่าน้ำหนัก (Weight) ของผลงานแต่ละชิ้น
    ตามประกาศ ม.อุบลฯ พ.ศ. 2567
    """
    # 1. Data Cleaning
    def clean(text):
        if not text: return ""
        return text.strip().replace(".", "")

    work_type = clean(work_type)
    work_level = clean(work_level)
    role = clean(role)

    # 2. Determine Weight (W) - ตามข้อ 6
    # Group 1 (Weight 1.0): First, Corresponding, Main
    # Group 2 (Weight 0.5): Essential Intellectual, Co-author
    
    weight = 0.0
    # Map from frontend values or Thai text
    if role in ['first', 'corresponding', 'main', 'แรก', 'บรรณกิจ', 'หลัก']:
        weight = 1.0
    elif role in ['intellectual', 'co', 'essential', 'ร่วม', 'มีส่วนสำคัญทางปัญญา']:
        weight = 0.5
    
    # 3. Determine Score (S) - ตามข้อ 5
    score = 0.0
    
    # Mapping Types
    if 'วิจัย' in work_type: # (1) บทความงานวิจัย
        if 'Q1' in work_level or 'Q2' in work_level: score = 1.25
        elif 'นานาชาติ' in work_level: score = 1.00 # นานาชาติอื่น
        elif 'ระดับชาติ' in work_level: score = 0.75

    elif 'ตำรา' in work_type or 'หนังสือ' in work_type: # (2) ตำรา/หนังสือ
        if 'สำนักพิมพ์' in work_level or 'inter' in work_level: score = 1.25
        elif 'โรงพิมพ์' in work_level or 'local' in work_level: score = 1.00

    elif 'สร้างสรรค์' in work_type: # (3) งานสร้างสรรค์
        if 'นานาชาติ' in work_level: score = 1.25
        elif 'ความร่วมมือ' in work_level: score = 1.00
        elif 'ระดับชาติ' in work_level: score = 0.75

    # (4)-(8) กลุ่มที่ใช้ระดับ A+, A, B
    # work_type: สังคม, อุตสาหกรรม, การสอน, นโยบาย, นวัตกรรม
    elif any(x in work_type for x in ['สังคม', 'ท้องถิ่น', 'อุตสาหกรรม', 'การสอน', 'นโยบาย', 'นวัตกรรม']):
        if 'A+' in work_level: score = 1.25
        elif 'A' in work_level: score = 1.00 # Matches 'A' but not 'A+' due to order
        elif 'B' in work_level: score = 0.75

    # Safety Check
    if weight == 0.0 or score == 0.0:
        return {
            "error": True,
            "message": "ข้อมูลไม่ครบถ้วน (Weight หรือ Score เป็น 0)",
            "score": score, "weight": weight, "final_score": 0
        }

    # 4. Calculate Final Score (ข้อ 7)
    final_score = score * weight

    return {
        "error": False,
        "score": score,
        "weight": weight,
        "final_score": final_score
    }

def calculate_money(total_score, position):
    """
    คำนวณเงินค่าตอบแทนจากคะแนนรวม (Total Score) และตำแหน่งทางวิชาการ
    ตามข้อ 8
    """
    position = position.strip().replace(".", "")
    compensation = 0

    # Normalize Position Checking
    # Asst Prof (ผศ.)
    if position.startswith('ผศ'):
        # ระดับ 1: 0.50 - 0.74 -> 3,000
        if 0.50 <= total_score <= 0.74: compensation = 3000
        # ระดับ 2: 0.75 ขึ้นไป -> 5,600
        elif total_score >= 0.75: compensation = 5600
        
    # Assoc Prof (รศ.)
    elif position.startswith('รศ'):
        # ระดับ 1: 0.75 - 1.24 -> 6,000
        if 0.75 <= total_score <= 1.24: compensation = 6000
        # ระดับ 2: 1.25 ขึ้นไป -> 9,900
        elif total_score >= 1.25: compensation = 9900
        
    # Prof (ศ.)
    elif position.startswith('ศ'):
        # ระดับ 1: 1.25 - 1.49 -> 9,000
        if 1.25 <= total_score <= 1.49: compensation = 9000
        # ระดับ 2: 1.50 ขึ้นไป -> 13,000
        elif total_score >= 1.50: compensation = 13000
    
    return compensation


@app.route('/')
def index():
    if 'username' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        users = load_data('users.json')
        user = next((u for u in users if u['username'] == username and u['password'] == password), None)
        if user:
            session.update({'username': user['username'], 'role': user['role'], 'name': user['name']})
            return redirect(url_for('dashboard'))
        flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect(url_for('login'))
    all_reqs = load_data('requests.json')
    if session['role'] == 'applicant':
        display_reqs = [r for r in all_reqs if r['applicant'] == session['username']]
    elif session['role'] == 'administration':
        display_reqs = [r for r in all_reqs if r['status'] in ['ส่งแล้ว', 'ผลงานซ้ำซ้อน', 'ผลงานถูกต้อง', 'รอตรวจสอบผลงาน', 'รอการพิจารณา', 'อนุมัติ', 'ไม่ผ่าน', 'รอการอุทธรณ์']]
    elif session['role'] == 'research':
        display_reqs = [r for r in all_reqs if r['status'] == 'รอตรวจสอบผลงาน']
    elif session['role'] == 'committee':
        display_reqs = [r for r in all_reqs if r['status'] in ['รอการพิจารณา', 'รอการอุทธรณ์']]
    else:
        display_reqs = []
    return render_template('dashboard.html', name=session['name'], role=session['role'], requests=display_reqs)

@app.route('/new_request', methods=['GET', 'POST'])
def new_request():
    if 'username' not in session or session['role'] != 'applicant': return redirect(url_for('login'))
    
    can_submit = is_within_timeline()
    criteria = load_config('criteria.json')

    today = datetime.now()
    fiscal_year = today.year + 543 if today.month >= 10 else today.year + 543
    
    users = load_data('users.json')
    user_profile = next((u for u in users if u['username'] == session['username']), {})

    # Check for edit mode
    edit_id = request.args.get('edit_id')
    edit_req = None
    if edit_id:
        all_reqs = load_data('requests.json')
        edit_req = next((r for r in all_reqs if r['id'] == edit_id and r['applicant'] == session['username']), None)

    if request.method == 'POST':
        action = request.form.get('action')
        
        # Handle traditional form submit or checks
        if action == 'submit' and not can_submit:
             flash("ไม่อยู่ในช่วงเวลาที่เปิดรับคำขอ")
             return redirect(url_for('new_request'))

        # Prepare Request Data
        # For this complex form, we expect works to be gathered via JS and sent as JSON or structured form data
        # Let's assume we handle standard form submission but parse dynamic fields
        
        # Basic Info
        req_id = request.form.get('req_id') or f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Works Processing
        # Works Processing
        works_json = request.form.get('works_data')
        works = json.loads(works_json) if works_json else []

        total_score = 0
        applicant_position = request.form.get('academic_position') or user_profile.get('academic_position', '')

        for work in works:
            # Extract details from the specific structure sent by frontend
            details = work.get('details', {})
            
            # 1. Map Work Type
            raw_type = work.get('type', '')
            w_type = raw_type # Default fallback
            
            if raw_type == 'research': w_type = 'บทความวิจัย'
            elif raw_type == 'textbook': w_type = 'ตำรา'
            elif raw_type == 'creative': w_type = 'งานสร้างสรรค์'
            elif raw_type == 'social' or raw_type == 'local': w_type = 'สังคม' # ท้องถิ่น/สังคม
            elif raw_type == 'industry': w_type = 'อุตสาหกรรม'
            elif raw_type == 'teaching': w_type = 'การสอน'
            elif raw_type == 'policy': w_type = 'นโยบาย'
            elif raw_type == 'innovation': w_type = 'นวัตกรรม'
            elif raw_type == 'patent': w_type = 'นวัตกรรม' # Fallback

            # 2. Map Work Level/Database
            # Frontend uses different keys for different types. 'database' is prioritized (used for Level A+/A/B)
            raw_level = details.get('database') or details.get('publish_type') or details.get('type') or ''
            w_level = raw_level # Default fallback
            
            # Research Mapping
            if raw_level == 'scopus_q1_q2': w_level = 'Q1 Q2'
            elif raw_level == 'scopus_other': w_level = 'นานาชาติ'
            elif raw_level == 'national': w_level = 'ระดับชาติ'
            
            # Textbook Mapping
            elif raw_level == 'inter': w_level = 'สำนักพิมพ์' # International Publisher
            elif raw_level == 'local': w_level = 'โรงพิมพ์'
            
            # Creative Mapping
            elif 'inter' in raw_level: w_level = 'นานาชาติ'
            elif 'coop' in raw_level: w_level = 'ความร่วมมือ'
            elif 'national' in raw_level: w_level = 'ระดับชาติ'

            # 3. Map Role
            raw_role = details.get('contribution', '')
            w_role = 'ร่วม' # Default to Co-author (0.5)
            if raw_role in ['first', 'corresponding', 'main']: 
                w_role = 'แรก' # First Author (1.0)
            
            # Calculate details (Score Only)
            calc_res = calculate_work_score(w_type, w_level, w_role)
            
            # Attach to work item for saving
            work['calculated_score'] = calc_res['score']
            work['calculated_weight'] = calc_res['weight']
            work['net_score'] = calc_res['final_score']
            # work['compensation'] is not calculated per item anymore
            work['calc_error'] = calc_res.get('error', False)
            work['calc_message'] = calc_res.get('message', '')

            if not calc_res.get('error'):
                total_score += calc_res['final_score']
        
        # Calculate Total Compensation based on SUM of scores
        total_compensation = calculate_money(total_score, applicant_position)
        
        req_data = {
            "id": req_id,
            "applicant": session['username'],
            "applicant_name": session['name'],
            "applicant_info": {
                "title_name": user_profile.get('title_name', ''),
                "academic_position": applicant_position,
                "position_date": user_profile.get('position_date', ''),
                "position_number": user_profile.get('position_number', ''),
                "department": user_profile.get('department', ''),
                "faculty": user_profile.get('faculty', '')
            },
            "fiscal_year": request.form.get('fiscal_year_req'),
            "works": works,
            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status": "ส่งแล้ว" if action == "submit" else "แบบร่าง",
            "score": total_score,
            "total_compensation": total_compensation, 
            "comment": "",
            "timeline_status": "ontime" if can_submit else "late",
            "certify": True if request.form.get('certify') else False
        }
        
        all_reqs = load_data('requests.json')
        
        # Update if exists, else append
        existing_idx = next((i for i, r in enumerate(all_reqs) if r['id'] == req_id), -1)
        if existing_idx > -1:
            # Preserve some fields if needed, or just overwrite for Draft logic
            all_reqs[existing_idx].update(req_data)
        else:
            all_reqs.append(req_data)
            
        save_data('requests.json', all_reqs)
        flash("บันทึกข้อมูลเรียบร้อยแล้ว")
        return redirect(url_for('dashboard'))
    
    timeline = load_config('timeline.json', {})
    return render_template('new_request.html', name=session['name'], role=session['role'], can_submit=can_submit, criteria=criteria, timeline=timeline, user=user_profile, edit_req=edit_req)

@app.route('/view_request/<req_id>', methods=['GET', 'POST'])
def view_request(req_id):
    if 'username' not in session: return redirect(url_for('login'))
    all_reqs = load_data('requests.json')
    req_data = next((r for r in all_reqs if r['id'] == req_id), None)
    
    if not req_data:
        flash("ไม่พบข้อมูลคำขอ")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')
        
        # Applicant Actions
        if req_data['status'] == 'แบบร่าง' and session['role'] == 'applicant':
            req_data['title'] = request.form.get('title')
            req_data['category'] = request.form.get('category')
            req_data['evidence'] = request.form.get('evidence_link')
            req_data['status'] = "ส่งแล้ว" if action == "submit" else "แบบร่าง"
            req_data['date'] = datetime.now().strftime("%d/%m/%Y %H:%M")
            save_data('requests.json', all_reqs)
            flash("อัปเดตข้อมูลเรียบร้อยแล้ว")
            return redirect(url_for('dashboard'))
        
        # Administration Actions
        elif req_data['status'] in ['ส่งแล้ว', 'ผลงานถูกต้อง', 'ผลงานซ้ำซ้อน'] and session['role'] == 'administration':
            if action == 'return':
                req_data['status'] = 'แก้ไข'
                req_data['comment'] = request.form.get('comment')
                flash("ส่งคืนคำขอให้ผู้ยื่นแก้ไขแล้ว")
            elif action == 'pass':
                req_data['status'] = 'รอตรวจสอบผลงาน'
                flash("ส่งต่อให้งานวิจัยเรียบร้อยแล้ว")
            elif action == 'to_committee':
                req_data['status'] = 'รอการพิจารณา'
                flash("ส่งต่อให้คณะกรรมการเรียบร้อยแล้ว")
            elif action == 'reject':
                req_data['status'] = 'ไม่ผ่าน'
                req_data['comment'] = request.form.get('comment')
                req_data['rejection_date'] = datetime.now().strftime("%d/%m/%Y")
                flash("ปฏิเสธคำขอเรียบร้อยแล้ว")
            save_data('requests.json', all_reqs)
            return redirect(url_for('dashboard'))

        # Research Actions
        elif req_data['status'] == 'รอตรวจสอบผลงาน' and session['role'] == 'research':
            if action == 'duplicate':
                req_data['status'] = 'ผลงานซ้ำซ้อน'
                req_data['comment'] = "ผลงานนี้เคยถูกใช้ขอค่าตอบแทนแล้ว"
                # Research sends to Admin, not direct rejection, so no date yet.
                flash("แจ้งผลงานซ้ำซ้อนไปยังงานบริหารแล้ว")
            elif action == 'verify':
                req_data['status'] = 'ผลงานถูกต้อง'
                flash("แจ้งผลงานถูกต้องไปยังงานบริหารแล้ว")
            save_data('requests.json', all_reqs)
            return redirect(url_for('dashboard'))

        # Committee Actions
        elif req_data['status'] in ['รอการพิจารณา', 'รอการอุทธรณ์'] and session['role'] == 'committee':
            if action == 'approve':
                req_data['status'] = 'อนุมัติ'
                req_data['approved_amount'] = request.form.get('amount')
                if req_data.get('status') == 'รอการอุทธรณ์':
                     if 'appeal' not in req_data: req_data['appeal'] = {}
                     req_data['appeal']['status'] = 'อนุมัติ'
                flash("อนุมัติคำขอเรียบร้อยแล้ว")
            elif action == 'reject':
                req_data['status'] = 'ไม่ผ่าน' # Appeal Rejected -> Final Reject
                req_data['comment'] = request.form.get('comment')
                req_data['rejection_date'] = datetime.now().strftime("%d/%m/%Y")
                if req_data.get('status') == 'รอการอุทธรณ์':
                     if 'appeal' not in req_data: req_data['appeal'] = {}
                     req_data['appeal']['status'] = 'ไม่ผ่าน'
                flash("ไม่อนุมัติคำขอ")
            save_data('requests.json', all_reqs)
            return redirect(url_for('dashboard'))

    return render_template('view_request.html', name=session['name'], role=session['role'], req=req_data)

@app.route('/appeal/<req_id>', methods=['GET', 'POST'])
def appeal_request(req_id):
    if 'username' not in session or session['role'] != 'applicant': return redirect(url_for('login'))
    all_reqs = load_data('requests.json')
    req_data = next((r for r in all_reqs if r['id'] == req_id), None)
    
    if not req_data or req_data['status'] != 'ไม่ผ่าน':
        flash("ไม่สามารถยื่นอุทธรณ์ได้สำหรับคำขอนี้")
        return redirect(url_for('view_request', req_id=req_id))

    # Check 7 Days Limit
    if 'rejection_date' in req_data:
        try:
            reject_dt = datetime.strptime(req_data['rejection_date'], "%d/%m/%Y")
            delta = datetime.now() - reject_dt
            if delta.days > 7:
                 flash("เกินกำหนดเวลาการยื่นอุทธรณ์ (7 วัน)")
                 return redirect(url_for('view_request', req_id=req_id))
        except: pass

    if request.method == 'POST':
        req_data['status'] = 'รอการอุทธรณ์'
        req_data['appeal'] = {
            "reason": request.form.get('reason'),
            "evidence": request.form.get('evidence_link'),
            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status": "รอพิจารณา"
        }
        save_data('requests.json', all_reqs)
        flash("ยื่นอุทธรณ์เรียบร้อยแล้ว")
        return redirect(url_for('view_request', req_id=req_id))

    return render_template('appeal_request.html', name=session['name'], role=session['role'], req=req_data)

@app.route('/manage', methods=['GET', 'POST'])
def manage_system():
    if 'username' not in session or session['role'] != 'admin': return redirect(url_for('login'))
    
    timeline = load_config('timeline.json', {})
    users = load_data('users.json')

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'save_timeline':
            timeline['fiscal_year'] = request.form.get('fiscal_year')
            timeline['start_date'] = request.form.get('start_date')
            timeline['end_date'] = request.form.get('end_date')
            save_data('timeline.json', timeline)
            flash("บันทึกการตั้งค่าเรียบร้อยแล้ว")
            
        elif action == 'add_user':
            username = request.form.get('username')
            if any(u['username'] == username for u in users):
                flash("ชื่อผู้ใช้นี้มีอยู่ในระบบแล้ว")
            else:
                new_user = {
                    "username": username,
                    "password": request.form.get('password'),
                    "name": request.form.get('name'),
                    "role": request.form.get('role')
                }
                users.append(new_user)
                save_data('users.json', users)
                flash(f"เพิ่มผู้ใช้งาน {username} เรียบร้อยแล้ว")
        
        elif action == 'delete_user':
            username_to_delete = request.form.get('username')
            if username_to_delete == session['username']:
                flash("ไม่สามารถลบบัญชีของตนเองได้")
            else:
                users = [u for u in users if u['username'] != username_to_delete]
                save_data('users.json', users)
                flash(f"ลบผู้ใช้งาน {username_to_delete} เรียบร้อยแล้ว")

        elif action == 'reset_password':
            username_to_reset = request.form.get('username')
            new_password = request.form.get('new_password')
            for user in users:
                if user['username'] == username_to_reset:
                    user['password'] = new_password
                    break
            save_data('users.json', users)
            flash(f"รีเซ็ตรหัสผ่านสำหรับ {username_to_reset} เรียบร้อยแล้ว")
            
        return redirect(url_for('manage_system'))

    return render_template('manage_system.html', name=session['name'], role=session['role'], timeline=timeline, users=users)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)