from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timedelta
import calendar

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
db = SQLAlchemy(app)

class Goal(db.Model):
    __tablename__ = 'goal'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    amount = db.Column(db.Float, nullable=False)
    income_per_pay_day = db.Column(db.Float, nullable=False)

    def remaining_pay_days(self):
        today = datetime.utcnow().date()
        goal_date = self.date
        pay_days = 0

        def is_last_day_of_month(date):
            next_day = date + timedelta(days=1)
            return next_day.day == 1

        while today <= goal_date:
            if today.day == 15 or is_last_day_of_month(today):
                pay_days += 1
            today += timedelta(days=1)

        return pay_days

    def amount_per_pay_day(self):
        remaining = self.remaining_pay_days()
        if remaining <= 0:
            return 0.0
        return self.amount / remaining

class PayProfile(db.Model):
    __tablename__ = 'pay_profile'
    id = db.Column(db.Integer, primary_key=True)
    net_pay = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(20), nullable=False)
    last_payday = db.Column(db.Date, nullable=False)

class SavingsGoal(db.Model):
    __tablename__ = 'savings_goal'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    target_date = db.Column(db.Date, nullable=False)
    priority = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

_db_initialized = False

def ensure_schema():
    global _db_initialized
    if _db_initialized:
        return
    db.create_all()
    try:
        with db.engine.connect() as connection:
            table = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='savings_goal'")
            ).fetchone()
            if table:
                columns = connection.execute(text("PRAGMA table_info(savings_goal)")).fetchall()
                column_names = {row[1] for row in columns}
                if 'is_active' not in column_names:
                    connection.execute(
                        text("ALTER TABLE savings_goal ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
                    )
    except Exception:
        pass
    _db_initialized = True

def add_month(base_date):
    year = base_date.year + (base_date.month // 12)
    month = 1 if base_date.month == 12 else base_date.month + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(base_date.day, last_day)
    return base_date.replace(year=year, month=month, day=day)

def next_payday(current, frequency):
    if frequency == 'weekly':
        return current + timedelta(days=7)
    if frequency == 'bi-weekly':
        return current + timedelta(days=14)
    return add_month(current)

def count_remaining_paydays(last_payday, frequency, target_date, start_date=None):
    if not last_payday or not frequency or not target_date:
        return 0
    start_date = start_date or datetime.utcnow().date()
    if target_date < start_date:
        return 0
    current = last_payday
    while current < start_date:
        current = next_payday(current, frequency)
    count = 0
    while current <= target_date:
        count += 1
        current = next_payday(current, frequency)
    return count

@app.route('/')
def home():
    goals = Goal.query.all()
    goals_with_pay_days = [(goal, goal.remaining_pay_days()) for goal in goals]
    total_amount_per_pay_day = sum(goal.amount_per_pay_day() for goal in goals)
    return render_template('index.html', goals=goals_with_pay_days, total_amount_per_pay_day=total_amount_per_pay_day)

@app.route('/goals')
def goals():
    ensure_schema()
    profile = PayProfile.query.first()
    goals = SavingsGoal.query.order_by(SavingsGoal.priority.asc(), SavingsGoal.target_date.asc()).all()

    total_savings = profile.net_pay if profile else 0.0
    allocations = []
    scores = []
    total_required = 0.0

    for goal in goals:
        remaining_paydays = None
        required_per_paycheck = None
        if profile and goal.is_active:
            remaining_paydays = count_remaining_paydays(profile.last_payday, profile.frequency, goal.target_date)
            if remaining_paydays > 0:
                required_per_paycheck = goal.target_amount / remaining_paydays
            else:
                required_per_paycheck = goal.target_amount
        priority_value = goal.priority if goal.priority and goal.priority > 0 else 1
        score = (required_per_paycheck or 0.0) / priority_value if goal.is_active else 0.0
        scores.append(score)
        total_required += required_per_paycheck or 0.0
        allocations.append({
            'goal': goal,
            'remaining_paydays': remaining_paydays,
            'required_per_paycheck': required_per_paycheck,
            'recommended_per_paycheck': 0.0,
            'priority_weight': priority_value,
        })

    score_total = sum(scores)
    for index, allocation in enumerate(allocations):
        if total_savings > 0 and score_total > 0:
            allocation['recommended_per_paycheck'] = total_savings * (scores[index] / score_total)

    chart_labels = [
        allocation['goal'].name for allocation in allocations if allocation['goal'].is_active
    ]
    chart_values = [
        round(allocation['recommended_per_paycheck'], 2)
        for allocation in allocations
        if allocation['goal'].is_active
    ]
    gap = (total_savings - total_required) if profile else None

    return render_template(
        'goals.html',
        profile=profile,
        goals=goals,
        allocations=allocations,
        total_savings=total_savings,
        total_required=total_required,
        gap=gap,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )

@app.route('/add_goal', methods=['POST'])
def add_goal():
    date = request.form['date']
    amount = request.form['amount']
    income_per_pay_day = request.form['incomePerPayDay']
    new_goal = Goal(date=datetime.strptime(date, '%Y-%m-%d'), amount=float(amount), income_per_pay_day=float(income_per_pay_day))
    db.session.add(new_goal)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/save_profile', methods=['POST'])
def save_profile():
    ensure_schema()
    net_pay = float(request.form['netPay'])
    frequency = request.form['frequency']
    last_payday = datetime.strptime(request.form['lastPayday'], '%Y-%m-%d').date()
    profile = PayProfile.query.first()
    if profile:
        profile.net_pay = net_pay
        profile.frequency = frequency
        profile.last_payday = last_payday
    else:
        profile = PayProfile(net_pay=net_pay, frequency=frequency, last_payday=last_payday)
        db.session.add(profile)
    db.session.commit()
    return redirect(url_for('goals'))

@app.route('/add_savings_goal', methods=['POST'])
def add_savings_goal():
    ensure_schema()
    name = request.form['name']
    target_amount = float(request.form['targetAmount'])
    target_date = datetime.strptime(request.form['targetDate'], '%Y-%m-%d').date()
    priority = int(request.form['priority'])
    new_goal = SavingsGoal(
        name=name,
        target_amount=target_amount,
        target_date=target_date,
        priority=priority,
        is_active=True,
    )
    db.session.add(new_goal)
    db.session.commit()
    return redirect(url_for('goals'))

@app.route('/delete_savings_goal/<int:id>', methods=['POST'])
def delete_savings_goal(id):
    ensure_schema()
    goal = SavingsGoal.query.get_or_404(id)
    db.session.delete(goal)
    db.session.commit()
    return redirect(url_for('goals'))

@app.route('/toggle_savings_goal/<int:id>', methods=['POST'])
def toggle_savings_goal(id):
    ensure_schema()
    goal = SavingsGoal.query.get_or_404(id)
    goal.is_active = bool(request.form.get('isActive'))
    db.session.commit()
    return redirect(url_for('goals'))

@app.route('/reorder_savings_goals', methods=['POST'])
def reorder_savings_goals():
    ensure_schema()
    payload = request.get_json(silent=True) or {}
    order = payload.get('order', [])
    if not isinstance(order, list):
        return {'error': 'Invalid order payload'}, 400
    ids = []
    for item in order:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    if not ids:
        return {'error': 'No goal ids provided'}, 400
    goals = SavingsGoal.query.filter(SavingsGoal.id.in_(ids)).all()
    goal_map = {goal.id: goal for goal in goals}
    for index, goal_id in enumerate(ids):
        goal = goal_map.get(goal_id)
        if goal:
            goal.priority = index + 1
    db.session.commit()
    return {'status': 'ok'}, 200

@app.route('/delete_goal/<int:id>', methods=['POST'])
def delete_goal(id):
    goal = Goal.query.get_or_404(id)
    db.session.delete(goal)
    db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
