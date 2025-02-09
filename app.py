from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

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
        return self.amount / self.remaining_pay_days()

@app.route('/')
def home():
    goals = Goal.query.all()
    goals_with_pay_days = [(goal, goal.remaining_pay_days()) for goal in goals]
    total_amount_per_pay_day = sum(goal.amount_per_pay_day() for goal in goals)
    return render_template('index.html', goals=goals_with_pay_days, total_amount_per_pay_day=total_amount_per_pay_day)

@app.route('/add_goal', methods=['POST'])
def add_goal():
    date = request.form['date']
    amount = request.form['amount']
    income_per_pay_day = request.form['incomePerPayDay']
    new_goal = Goal(date=datetime.strptime(date, '%Y-%m-%d'), amount=float(amount), income_per_pay_day=float(income_per_pay_day))
    db.session.add(new_goal)
    db.session.commit()
    return redirect(url_for('home'))

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