from SimulatedRobot import *
from IndexStruct import *
from Pose3D import *
import scipy
from roboticstoolbox.mobile.Animations import *
import numpy as np


class DifferentialDriveSimulatedRobot(SimulatedRobot):
    """
    This class implements a simulated differential drive robot. It inherits from the :class:`SimulatedRobot` class and
    overrides some of its methods to define the differential drive robot motion model.
    """
    def __init__(self, xs0, map=[],*args):
        """
        :param xs0: initial simulated robot state :math:`\\mathbf{x_{s_0}}=[^Nx{_{s_0}}~^Ny{_{s_0}}~^N\psi{_{s_0}}~]^T` used to initialize the  motion model
        :param map: feature map of the environment :math:`M=[^Nx_{F_1},...,^Nx_{F_{nf}}]`

        Initializes the simulated differential drive robot. Overrides some of the object attributes of the parent class :class:`SimulatedRobot` to define the differential drive robot motion model:

        * **Qsk** : Object attribute containing Covariance of the simulation motion model noise.

        .. math::
            Q_k=\\begin{bmatrix}\\sigma_{\\dot u}^2 & 0 & 0\\\\
            0 & \\sigma_{\\dot v}^2 & 0 \\\\
            0 & 0 & \\sigma_{\\dot r}^2 \\\\
            \\end{bmatrix}
            :label: eq:Qsk

        * **usk** : Object attribute containing the simulated input to the motion model containing the forward velocity :math:`u_k` and the angular velocity :math:`r_k`

        .. math::
            \\bf{u_k}=\\begin{bmatrix}u_k & r_k\\end{bmatrix}^T
            :label: eq:usk

        * **xsk** : Object attribute containing the current simulated robot state

        .. math::
            x_k=\\begin{bmatrix}{^N}x_k & {^N}y_k & {^N}\\theta_k & {^B}u_k & {^B}v_k & {^B}r_k\\end{bmatrix}^T
            :label: eq:xsk

        where :math:`{^N}x_k`, :math:`{^N}y_k` and :math:`{^N}\\theta_k` are the robot position and orientation in the world N-Frame, and :math:`{^B}u_k`, :math:`{^B}v_k` and :math:`{^B}r_k` are the robot linear and angular velocities in the robot B-Frame.

        * **zsk** : Object attribute containing :math:`z_{s_k}=[n_L~n_R]^T` observation vector containing number of pulses read from the left and right wheel encoders.
        * **Rsk** : Object attribute containing :math:`R_{s_k}=diag(\\sigma_L^2,\\sigma_R^2)` covariance matrix of the noise of the read pulses`.
        * **wheelBase** : Object attribute containing the distance between the wheels of the robot (:math:`w=0.5` m)
        * **wheelRadius** : Object attribute containing the radius of the wheels of the robot (:math:`R=0.1` m)
        * **pulses_x_wheelTurn** : Object attribute containing the number of pulses per wheel turn (:math:`pulseXwheelTurn=1024` pulses)
        * **Polar2D_max_range** : Object attribute containing the maximum Polar2D range (:math:`Polar2D_max_range=50` m) at which the robot can detect features.
        * **Polar2D\_feature\_reading\_frequency** : Object attribute containing the frequency of Polar2D feature readings (50 tics -sample times-)
        * **Rfp** : Object attribute containing the covariance of the simulated Polar2D feature noise (:math:`R_{fp}=diag(\\sigma_{\\rho}^2,\\sigma_{\\phi}^2)`)

        Check the parent class :class:`prpy.SimulatedRobot` to know the rest of the object attributes.
        """
        super().__init__(xs0, map,*args) # call the parent class constructor

        # Initialize the motion model noise
        self.Qsk = np.diag(np.array([0.1 ** 2, 0.01 ** 2, np.deg2rad(1) ** 2]))  # simulated acceleration noise
        # self.Qsk = np.diag(np.array([0, 0, 0]))  # simulated acceleration noise
        self.usk = np.zeros((3, 1))  # simulated input to the motion model

        # Inititalize the robot parameters
        self.wheelBase = 0.5  # distance between the wheels
        self.wheelRadius = 0.1  # radius of the wheels
        self.pulse_x_wheelTurns = 1024  # number of pulses per wheel turn
        self.encoder_readings = np.array([[0, 0]], dtype=np.float32).T

        # Initialize the sensor simulation
        self.encoder_reading_frequency = 1  # frequency of encoder readings
        self.Re= np.diag(np.array([22 ** 2, 22 ** 2]))  # covariance of simulated wheel encoder noise
        # self.Re= np.diag(np.array([40 ** 2, 40 ** 2]))  # covariance of simulated wheel encoder noise
        # self.Re= np.diag(np.array([0, 0]))  # covariance of simulated wheel encoder noise

        self.Polar2D_feature_reading_frequency = 50  # frequency of Polar2D feature readings
        self.Polar2D_max_range = 50  # maximum Polar2D range, used to simulate the field of view
        self.Rfp = np.diag(np.array([1 ** 2, np.deg2rad(5) ** 2]))  # covariance of simulated Polar2D feature noise

        self.xy_feature_reading_frequency = 50  # frequency of XY feature readings
        self.xy_max_range = 50  # maximum XY range, used to simulate the field of view
        self.Rdist_std = 0.5 # standard deviation of range readings noise

        self.yaw_reading_frequency = 1  # frequency of Yaw readings
        self.v_yaw_std = np.deg2rad(5)  # std deviation of simulated heading noise

    def fs(self, xsk_1, usk):  # input velocity motion model with velocity noise
        """ Motion model used to simulate the robot motion. Computes the current robot state :math:`x_k` given the previous robot state :math:`x_{k-1}` and the input :math:`u_k`:

        .. math::
            \\eta_{s_{k-1}}&=\\begin{bmatrix}x_{s_{k-1}} & y_{s_{k-1}} & \\theta_{s_{k-1}}\\end{bmatrix}^T\\\\
            \\nu_{s_{k-1}}&=\\begin{bmatrix} u_{s_{k-1}} &  v_{s_{k-1}} & r_{s_{k-1}}\\end{bmatrix}^T\\\\
            x_{s_{k-1}}&=\\begin{bmatrix}\\eta_{s_{k-1}}^T & \\nu_{s_{k-1}}^T\\end{bmatrix}^T\\\\
            u_{s_k}&=\\nu_{d}=\\begin{bmatrix} u_d& r_d\\end{bmatrix}^T\\\\
            w_{s_k}&=\\dot \\nu_{s_k}\\\\
            x_{s_k}&=f_s(x_{s_{k-1}},u_{s_k},w_{s_k}) \\\\
            &=\\begin{bmatrix}
            \\eta_{s_{k-1}} \\oplus (\\nu_{s_{k-1}}\\Delta t + \\frac{1}{2} w_{s_k}) \\\\
            \\nu_{s_{k-1}}+K(\\nu_{d}-\\nu_{s_{k-1}}) + w_{s_k} \\Delta t
            \\end{bmatrix} \\quad;\\quad K=diag(k_1,k_2,k_3) \\quad k_i>0\\\\
            :label: eq:fs

        Where :math:`\\eta_{s_{k-1}}` is the previous 3 DOF robot pose (x,y,yaw) and :math:`\\nu_{s_{k-1}}` is the previous robot velocity (velocity in the direction of x and y B-Frame axis of the robot and the angular velocity).
        :math:`u_{s_k}` is the input to the motion model contaning the desired robot velocity in the x direction (:math:`u_d`) and the desired angular velocity around the z axis (:math:`r_d`).
        :math:`w_{s_k}` is the motion model noise representing an acceleration perturbation in the robot axis. The :math:`w_{s_k}` acceleration is the responsible for the slight velocity variation in the simulated robot motion.
        :math:`K` is a diagonal matrix containing the gains used to drive the simulated velocity towards the desired input velocity.

        Finally, the class updates the object attributes :math:`xsk`, :math:`xsk\_1` and  :math:`usk` to made them available for plotting purposes.

        **To be completed by the student**.

        :parameter xsk_1: previous robot state :math:`x_{s_{k-1}}=\\begin{bmatrix}\\eta_{s_{k-1}}^T & \\nu_{s_{k-1}}^T\\end{bmatrix}^T`
        :parameter usk: model input :math:`u_{s_k}=\\nu_{d}=\\begin{bmatrix} u_d& r_d\\end{bmatrix}^T`
        :return: current robot state :math:`x_{s_k}`
        """

        eta_sk_1 = Pose3D(xsk_1[:3])
        nu_sk_1 = Pose3D(xsk_1[3:6])
        nu_d = np.array([[usk[0][0], 0, usk[1][0]]]).T

        wsk = np.reshape(np.random.normal(np.zeros_like(self.Qsk), self.Qsk).diagonal(), (3, 1))

        eta_operand = nu_sk_1 * self.dt + 0.5 * wsk * self.dt ** 2
        eta_sk = eta_sk_1.oplus(eta_operand)

        K = np.diag(np.array([1, 1, 1]))

        nu_sk = nu_sk_1 + np.matmul(K, (nu_d - nu_sk_1)) + wsk * self.dt

        self.xsk = np.concatenate([eta_sk, nu_sk])

        # Convert forward and angular velocity into wheel velocity, to compute distance travelled by the wheel
        fwd_velocity, angular_velocity = usk[0][0], usk[1][0]
        radius = self.wheelBase / 2
        wheel_velocity = (
             np.full_like(self.encoder_readings, fwd_velocity) + # forward velocity component
             radius * np.array([[-angular_velocity, angular_velocity]]).T # angular velocity component
             )
        wheel_distance = self.dt * wheel_velocity
        self.encoder_readings += np.round(wheel_distance * self.pulse_x_wheelTurns / (2 * pi * self.wheelRadius))

        if self.k % self.visualizationInterval == 0:
                self.PlotRobot()
                self.xTraj.append(self.xsk[0, 0])
                self.yTraj.append(self.xsk[1, 0])
                self.trajectory.pop(0).remove()
                self.trajectory = plt.plot(self.xTraj, self.yTraj, marker='.', color='orange', markersize=1)

        self.k += 1
        return self.xsk


    def ReadEncoders(self):
        """ Simulates the robot measurements of the left and right wheel encoders.

        **To be completed by the student**.

        :return zsk,Rsk: :math:`zk=[n_L~n_R]^T` observation vector containing number of pulses read from the left and right wheel encoders. :math:`R_{s_k}=diag(\\sigma_L^2,\\sigma_R^2)` covariance matrix of the read pulses.
        """
        noise = np.reshape(np.random.normal(0, self.Re).diagonal(), (2, 1)).round().astype(np.int32)
        return self.encoder_readings + noise, self.Re
        

    def ReadCompass(self):
        """ Simulates the compass reading of the robot.

        :return: yaw and the covariance of its noise *R_yaw*
        """
        double_pi = 2 * np.pi
        raw_compass_value = self.xsk[2, 0] + np.random.normal(0, self.v_yaw_std)
        if raw_compass_value >= double_pi or raw_compass_value < 0:
            raw_compass_value -= double_pi * (raw_compass_value // double_pi)

        return raw_compass_value, self.v_yaw_std
    

    def ReadRanges(self):
        """ Simulates reading the distances to the features in the environment.

        return: distance to each of the features
        """

        features_and_distances = []
        for f in self.M:
            actual_distance = np.linalg.norm(self.xsk[:2] - f)
            if actual_distance > self.xy_max_range:
                # Outside range
                continue
            
            noise = np.random.normal(0, self.Rdist_std)
            features_and_distances.append((f, actual_distance + noise))

        return features_and_distances
        

    def PlotRobot(self):
        """ Updates the plot of the robot at the current pose """

        self.vehicleIcon.update([self.xsk[0], self.xsk[1], self.xsk[2]])
        plt.pause(0.0000001)
        return


def __run_robot(robot: SimulatedRobot, steps: int, forward_velocity: float, angular_velocity: float):
    usk = np.array([[forward_velocity, angular_velocity]]).T
    for _ in range(steps):
        robot.fs(robot.xsk, usk)


def run_circle():
    robot = DifferentialDriveSimulatedRobot(np.zeros((6, 1)))

    __run_robot(
        robot,
        steps=10000,
        forward_velocity=1,
        angular_velocity=0.01,
    )


def run_eight():
    robot = DifferentialDriveSimulatedRobot(np.zeros((6, 1)))

    d = 5

    steps = 500
    straight_steps = int(2 * steps)
    circle_steps = int(1.5 * pi * steps)

    base_velocity = 10 / steps
    forward_velocity = d * base_velocity
    angular_velocity = base_velocity

    for _ in range(3):
        __run_robot(robot, straight_steps, forward_velocity, 0)
        __run_robot(robot, circle_steps, forward_velocity, angular_velocity)
        __run_robot(robot, straight_steps, forward_velocity, 0)
        __run_robot(robot, circle_steps, forward_velocity, -angular_velocity)


def run_eight_simple():
    robot = DifferentialDriveSimulatedRobot(np.zeros((6, 1)))

    speed_factor = 1

    circle_steps = int(2 * pi * 1000 / speed_factor)

    forward_velocity = 0.1 * speed_factor
    angular_velocity = 0.01 * speed_factor

    for _ in range(3):
        __run_robot(robot, circle_steps, forward_velocity, angular_velocity)
        __run_robot(robot, circle_steps, forward_velocity, -angular_velocity)

if __name__ == "__main__":
    # run_circle()
    run_eight()
    # run_eight_simple()
