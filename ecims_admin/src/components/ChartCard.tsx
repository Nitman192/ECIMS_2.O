import React from 'react';
import { Card } from './ui/Card';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

// Mock data for Events per Hour
const eventsPerHourData = [
  { hour: '00', events: 12 },
  { hour: '01', events: 9 },
  { hour: '02', events: 7 },
  { hour: '03', events: 5 },
  { hour: '04', events: 8 },
  { hour: '05', events: 13 },
  { hour: '06', events: 18 },
  { hour: '07', events: 22 },
  { hour: '08', events: 30 },
  { hour: '09', events: 28 },
  { hour: '10', events: 25 },
  { hour: '11', events: 20 },
  { hour: '12', events: 15 },
  { hour: '13', events: 10 },
  { hour: '14', events: 8 },
  { hour: '15', events: 12 },
  { hour: '16', events: 17 },
  { hour: '17', events: 23 },
  { hour: '18', events: 27 },
  { hour: '19', events: 29 },
  { hour: '20', events: 24 },
  { hour: '21', events: 19 },
  { hour: '22', events: 14 },
  { hour: '23', events: 11 },
];

// Mock data for Rollout Distribution
const rolloutData = [
  { name: 'Strict', value: 400 },
  { name: 'Permissive', value: 300 },
  { name: 'Monitor', value: 200 },
  { name: 'Disabled', value: 100 },
];
const COLORS = ['#10b981', '#6366f1', '#f59e42', '#ef4444'];

export const ChartCard = () => (
  <div className="grid gap-6 xl:grid-cols-2">
    <Card className="p-4">
      <h2 className="text-lg font-semibold mb-2">Events per Hour</h2>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={eventsPerHourData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="hour" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="events" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
    <Card className="p-4">
      <h2 className="text-lg font-semibold mb-2">Rollout Distribution</h2>
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie
            data={rolloutData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            fill="#8884d8"
            paddingAngle={3}
            dataKey="value"
            label
          >
            {rolloutData.map((entry, index) => (
              <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </Card>
  </div>
);

export default ChartCard;
