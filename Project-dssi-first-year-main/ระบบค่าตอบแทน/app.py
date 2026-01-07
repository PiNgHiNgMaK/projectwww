
กฟไไไไไไไไไไไไไไไไไไไไไไไไไไไไ
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
        works_json = request.form.get('works_data')
        works = json.loads(works_json) if works_json else []

        total_score = 0
        
        req_data = {
            "id": req_id,
            "applicant": session['username'],
            "applicant_name": session['name'],
            "applicant_info": {
                "title_name": user_profile.get('title_name', ''),
                "academic_position": user_profile.get('academic_position', ''),
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

    # Fetch applicant history for duplicate checking
    applicant_history = [r for r in all_reqs if r['applicant'] == req_data['applicant'] and r['id'] != req_id]
    
    return render_template('view_request.html', name=session['name'], role=session['role'], req=req_data, history=applicant_history)

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