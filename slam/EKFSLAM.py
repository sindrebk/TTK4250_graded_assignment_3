from typing import Tuple
import numpy as np
from numpy import ndarray, zeros
from dataclasses import dataclass, field
from scipy.linalg import block_diag
import scipy.linalg as la
from utils import rotmat2d
from JCBB import JCBB
import utils
import solution


@dataclass
class EKFSLAM:
    Q: ndarray
    R: ndarray
    do_asso: bool
    alphas: 'ndarray[2]' = field(default=np.array([0.001, 0.0001]))
    sensor_offset: 'ndarray[2]' = field(default=np.zeros(2))

    def f(self, x: np.ndarray, u: np.ndarray) -> np.ndarray:
        """Add the odometry u to the robot state x.

        Parameters
        ----------
        x : np.ndarray, shape=(3,)
            the robot state
        u : np.ndarray, shape=(3,)
            the odometry

        Returns
        -------
        np.ndarray, shape = (3,)
            the predicted state
        """

        #xpred_sol = solution.EKFSLAM.EKFSLAM.f(self, x, u)

        xpred = np.zeros(3)
        xpred[0:2] = x[0:2] + utils.rotmat2d(x[2]) @ u[0:2]
        xpred[2] = utils.wrapToPi(x[2] + u[2])


        return xpred

    def Fx(self, x: np.ndarray, u: np.ndarray) -> np.ndarray:
        """Calculate the Jacobian of f with respect to x.

        Parameters
        ----------
        x : np.ndarray, shape=(3,)
            the robot state
        u : np.ndarray, shape=(3,)
            the odometry

        Returns
        -------
        np.ndarray
            The Jacobian of f wrt. x.
        """
        # Fx_sol = solution.EKFSLAM.EKFSLAM.Fx(self, x, u)

        Fx = np.eye(3)
        Fx[0:2, 2:] = utils.rotmat2dDerivative(x[2]) @ np.expand_dims(u[0:2],  axis=1)

        return Fx

    def Fu(self, x: np.ndarray, u: np.ndarray) -> np.ndarray:
        """Calculate the Jacobian of f with respect to u.

        Parameters
        ----------
        x : np.ndarray, shape=(3,)
            the robot state
        u : np.ndarray, shape=(3,)
            the odometry

        Returns
        -------
        np.ndarray
            The Jacobian of f wrt. u.
        """
        # Fu = solution.EKFSLAM.EKFSLAM.Fu(self, x, u)

        Fu = np.eye(3)
        Fu[0:2, 0:2] = utils.rotmat2d(x[2])

        return Fu

    def predict(
        self, eta: np.ndarray, P: np.ndarray, z_odo: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predict the robot state using the zOdo as odometry the corresponding state&map covariance.

        Parameters
        ----------
        eta : np.ndarray, shape=(3 + 2*#landmarks,)
            the robot state and map concatenated
        P : np.ndarray, shape=(3 + 2*#landmarks,)*2
            the covariance of eta
        z_odo : np.ndarray, shape=(3,)
            the measured odometry

        Returns
        -------
        Tuple[np.ndarray, np.ndarray], shapes= (3 + 2*#landmarks,), (3 + 2*#landmarks,)*2
            predicted mean and covariance of eta.
        """
         
        # etapred_sol, P_sol = solution.EKFSLAM.EKFSLAM.predict(self, eta, np.copy(P), z_odo)
        # return etapred_sol, P_sol

        # check inout matrix
        # assert np.allclose(P, P.T), "EKFSLAM.predict: not symmetric P input"
        # assert np.all(
        #     np.linalg.eigvals(P) >= 0
        # ), "EKFSLAM.predict: non-positive eigen values in P input"
        # assert (
        #     eta.shape * 2 == P.shape
        # ), "EKFSLAM.predict: input eta and P shape do not match"

        etapred = np.empty_like(eta)

        x = eta[:3]
        etapred[:3] = self.f(x, z_odo)
        etapred[3:] = eta[3:]               # Landsmarks just pass through the prediction

        Fx = self.Fx(x, z_odo)
        Fu = self.Fu(x, z_odo)

        # evaluate covariance prediction in place to save computation
        # only robot state changes, so only rows and colums of robot state needs changing
        # cov matrix layout:
        # [[P_xx, P_xm],
        # [P_mx, P_mm]]

        # G = np.block([[np.eye(3)], [np.zeros((eta.size - 3, 3))]])
        # Q = self.Q

        # F = la.block_diag(Fx, np.eye( 2*( eta.size - 3)) )

        P[:3, :3] = Fx @ P[:3, :3] @ Fx.T + Fu @ self.Q @ Fu.T
        P[:3, 3:] = Fx @ P[:3, 3:]
        P[3:, :3] = P[:3, 3:].T

        #P[:3, :3] = F[:3, :3] @ P[:3, :3] @ F[:3, :3].T + G[:3, :3] @ Q[:3, :3] @ G[:3, :3].T

        return etapred, P

    def h(self, eta: np.ndarray) -> np.ndarray:
        """Predict all the landmark positions in sensor frame.

        Parameters
        ----------
        eta : np.ndarray, shape=(3 + 2 * #landmarks,)
            The robot state and landmarks stacked.

        Returns
        -------
        np.ndarray, shape=(2 * #landmarks,)
            The landmarks in the sensor frame.
        """

        # zpred_sol = solution.EKFSLAM.EKFSLAM.h(self, eta)

        # extract states and map
        x = eta[0:3]
        # reshape map (2, #landmarks), m[:, j] is the jth landmark
        m = eta[3:].reshape((-1, 2)).T

        Rot = rotmat2d(x[2])

        # None as index ads an axis with size 1 at that position.
        # Numpy broadcasts size 1 dimensions to any size when needed

        # Relative position of landmark to sensor on robot in world frame
        delta_m = m - np.reshape(x[:2], (2,1))

        # Predicted measurements in cartesian coordinates, beware sensor offset for VP
        zpredcart = delta_m - np.reshape(Rot @ self.sensor_offset, (2, 1))
        zpred_r = np.linalg.norm( zpredcart , axis=0)  # ranges
        zpos = Rot.T @ (zpredcart)
        zpred_theta = np.arctan2(zpos[1,:], zpos[0,:]) # bearings
        zpred = np.stack((zpred_r, zpred_theta))  

        # The two arrays above stacked on top of each other vertically like
        # [ranges;
        #  bearings]
        # into shape (2, #lmrk)

        # stack measurements along one dimension, [range1 bearing1 range2 bearing2 ...]
        zpred = zpred.T.ravel()

        # assert (
        #     zpred.ndim == 1 and zpred.shape[0] == eta.shape[0] - 3
        # ), "SLAM.h: Wrong shape on zpred"

        return zpred

    def h_jac(self, eta: np.ndarray) -> np.ndarray:
        """Calculate the jacobian of h.

        Parameters
        ----------
        eta : np.ndarray, shape=(3 + 2 * #landmarks,)
            The robot state and landmarks stacked.

        Returns
        -------
        np.ndarray, shape=(2 * #landmarks, 3 + 2 * #landmarks)
            the jacobian of h wrt. eta.
        """
        #H_sol = solution.EKFSLAM.EKFSLAM.h_jac(self, eta)

        # extract states and map
        x = eta[0:3]
        # reshape map (2, #landmarks), m[j] is the jth landmark
        m = eta[3:].reshape((-1, 2)).T

        numM = m.shape[1]

        Rot = rotmat2d(x[2])

        # Relative position of landmark to robot in world frame. m - rho that appears in (11.15) and (11.16)
        delta_m = m - np.reshape(x[:2], (2,1))

        # (2, #measurements), each measured position in cartesian coordinates like
        zc = delta_m - np.reshape(Rot @ self.sensor_offset, (2, 1))

        zpred_r = np.linalg.norm(zc, axis=0)  # ranges
        zpos = Rot.T @ (zc)
        zpred_theta = np.arctan2(zpos[1,:], zpos[0,:]) # bearings
        zpred = np.stack((zpred_r, zpred_theta))  

        Rpihalf = rotmat2d(np.pi / 2)
        max_range = np.max(zpred_r)

        # In what follows you can be clever and avoid making this for all the landmarks you _know_
        # you will not detect (the maximum range should be available from the data).
        # But keep it simple to begin with.

        # Allocate H and set submatrices as memory views into H
        # You may or may not want to do this like this
        # see eq (11.15), (11.16), (11.17)
        H = np.zeros((2 * numM, 3 + 2 * numM))
        Hx = H[:, :3]  # slice view, setting elements of Hx will set H as well
        Hm = H[:, 3:]  # slice view, setting elements of Hm will set H as well

        # proposed way is to go through landmarks one by one
        # preallocate and update this for some speed gain if looping
        jac_z_cb = -np.eye(2, 3)
        for i in range(numM):  # But this whole loop can be vectorized
            ind = 2 * i  # starting postion of the ith landmark into H
            # the inds slice for the ith landmark into H
            inds = slice(ind, ind + 2)
            col_inds = slice(3 + ind, 3 + ind + 2)

            m_i = m[0:2, i]
            rho_k = x[0:2]
            zc_i = np.reshape(zc[:, i], (2, 1))
            
            delta = m_i - rho_k
            diff = np.block([-np.eye(2), np.reshape(-Rpihalf @ delta, (2, 1))])

            Hx_i_r = (zc_i.T/np.linalg.norm(zc_i)) @ diff
            Hx_i_b = (zc_i.T @ Rpihalf.T) / (np.linalg.norm(zc_i) ** 2) @ diff

            Hx_i = np.block([[Hx_i_r],
                            [Hx_i_b]]) 

            Hm_i = -Hx_i[:2, :2]
            #Hm_i = 1 / (np.linalg.norm(delta) ** 2) * np.stack((np.linalg.norm(delta) * (delta).T, delta.T @ Rpihalf))

            
            H[inds, 0:3] = Hx_i
            H[inds, col_inds] = Hm_i
    
        return H

    def add_landmarks(
        self, eta: np.ndarray, P: np.ndarray, z: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate new landmarks, their covariances and add them to the state.

        Parameters
        ----------
        eta : np.ndarray, shape=(3 + 2*#landmarks,)
            the robot state and map concatenated
        P : np.ndarray, shape=(3 + 2*#landmarks,)*2
            the covariance of eta
        z : np.ndarray, shape(2 * #newlandmarks,)
            A set of measurements to create landmarks for

        Returns
        -------
        Tuple[np.ndarray, np.ndarray], shapes=(3 + 2*(#landmarks + #newlandmarks,), (3 + 2*(#landmarks + #newlandmarks,)*2
            eta with new landmarks appended, and its covariance
        """
        #etaadded_sol, Padded_sol = solution.EKFSLAM.EKFSLAM.add_landmarks(
        #    self, eta, P, z)
        #return etaadded_sol, Padded_sol

        n = P.shape[0]
        # assert z.ndim == 1, "SLAM.add_landmarks: z must be a 1d array"

        numLmk = z.shape[0] // 2

        lmnew = np.empty_like(z)

        Gx = np.empty((numLmk * 2, 3))
        Rall = np.zeros((numLmk * 2, numLmk * 2))

        I2 = np.eye(2)  # Preallocate, used for Gx
        # For transforming landmark position into world frame
        sensor_offset_world = rotmat2d(eta[2]) @ self.sensor_offset
        sensor_offset_world_der = rotmat2d(
            eta[2] + np.pi / 2) @ self.sensor_offset  # Used in Gx

        for j in range(numLmk):
            ind = 2 * j
            inds = slice(ind, ind + 2)
            zj = z[inds]

            # Rotmat in Gz
            rot = rotmat2d(zj[1] + eta[2])  

            # Calculate position of new landmark in world frame
            lmnew[inds] = zj[0]*rot[:,0] + eta[:2] + sensor_offset_world

            Gx[inds, :2] = I2
            Gx[inds, 2] = zj[0] * rot[:,1] + sensor_offset_world_der

            Gz = rot @ np.diag((1, zj[0])) 

            # Gz * R * Gz^T, transform measurement covariance from polar to cartesian coordinates
            Rall[inds, inds] = Gz @ self.R @ Gz.T

        # assert len(lmnew) % 2 == 0, "SLAM.add_landmark: lmnew not even length"

        # Append new landmarks to state vector
        etaadded = np.append(eta, lmnew.flatten(), axis=0)  

        # Block diagonal of P_new, see problem text in 1g) in graded assignment 3
        Padded = la.block_diag(P, Gx @ P[:3, :3] @ Gx.T + Rall)
        Padded[n:, :n] = Gx @ P[:3, :]  # top left corner of P_new

        # Transpose of above. Should yield the same as calcualion, but this 
        # enforces symmetry and should be cheaper
        Padded[:n, n:] = Padded[n:, :n].T

        # assert (
        #     etaadded.shape * 2 == Padded.shape
        # ), "EKFSLAM.add_landmarks: calculated eta and P has wrong shape"
        # assert np.allclose(
        #     Padded, Padded.T
        # ), "EKFSLAM.add_landmarks: Padded not symmetric"
        # assert np.all(
        #     np.linalg.eigvals(Padded) >= 0
        # ), "EKFSLAM.add_landmarks: Padded not PSD"
        return etaadded, Padded

    def associate(
        self, z: np.ndarray, zpred: np.ndarray, H: np.ndarray, S: np.ndarray,
    ):  # -> Tuple[*((np.ndarray,) * 5)]:
        """Associate landmarks and measurements, and extract correct matrices for these.

        Parameters
        ----------
        z : np.ndarray,
            The measurements all in one vector
        zpred : np.ndarray
            Predicted measurements in one vector
        H : np.ndarray
            The measurement Jacobian matrix related to zpred
        S : np.ndarray
            The innovation covariance related to zpred

        Returns
        -------
        Tuple[*((np.ndarray,) * 5)]
            The extracted measurements, the corresponding zpred, H, S and the associations.

        Note
        ----
        See the associations are calculated  using JCBB. See this function for documentation
        of the returned association and the association procedure.
        """
        if self.do_asso:
            # Associate
            a = JCBB(z, zpred, S, self.alphas[0], self.alphas[1])

            # Extract associated measurements
            zinds = np.empty_like(z, dtype=bool)
            zinds[::2] = a > -1  # -1 means no association
            zinds[1::2] = zinds[::2]
            zass = z[zinds]

            # extract and rearange predicted measurements and cov
            zbarinds = np.empty_like(zass, dtype=int)
            zbarinds[::2] = 2 * a[a > -1]
            zbarinds[1::2] = 2 * a[a > -1] + 1

            zpredass = zpred[zbarinds]
            Sass = S[zbarinds][:, zbarinds]
            Hass = H[zbarinds]

            # assert zpredass.shape == zass.shape
            # assert Sass.shape == zpredass.shape * 2
            # assert Hass.shape[0] == zpredass.shape[0]

            return zass, zpredass, Hass, Sass, a
        else:
            # should one do something her
            pass

    def update(
        self, eta: np.ndarray, P: np.ndarray, z: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        """Update eta and P with z, associating landmarks and adding new ones.

        Parameters
        ----------
        eta : np.ndarray
            [description]
        P : np.ndarray
            [description]
        z : np.ndarray, shape=(#detections, 2)
            [description]

        Returns
        -------
        Tuple[np.ndarray, np.ndarray, float, np.ndarray]
            [description]
        """
        
        # etaupd_sol, Pupd_sol, NIS_sol, a_sol = solution.EKFSLAM.EKFSLAM.update(self, eta, P, z)
        # return etaupd_sol, Pupd_sol, NIS_sol, a_sol

        numLmk = (eta.size - 3) // 2
        # assert (len(eta) - 3) % 2 == 0, "EKFSLAM.update: landmark lenght not even"

        if numLmk > 0:
            # Prediction and innovation covariance
            zpred = self.h(eta)
            H = self.h_jac(eta)

            # Here you can use simply np.kron (a bit slow) to form the big (very big in VP after a while) R,
            # or be smart with indexing and broadcasting (3d indexing into 2d mat) realizing you are adding the same R on all diagonals
            m, n = self.R.shape
            out = np.zeros((numLmk, m, numLmk, n), dtype=self.Q.dtype)
            diag = np.einsum('ijik->ijk',out)
            diag[:] = self.R
            R = out.reshape(-1,n*numLmk)
            S = H @ P @ H.T  + R
            # assert (
            #     S.shape == zpred.shape * 2
            # ), "EKFSLAM.update: wrong shape on either S or zpred"
            z = z.ravel()  # 2D -> flat

            # Perform data association
            za, zpred, Ha, Sa, a = self.associate(z, zpred, H, S)

            # No association could be made, so skip update
            if za.shape[0] == 0:
                etaupd = eta
                Pupd = P
                NIS = 1  # TODO: beware this one when analysing consistency.
            else:
                # Create the associated innovation
                v = za.ravel() - zpred  # za: 2D -> flat
                v[1::2] = utils.wrapToPi(v[1::2])

                # Kalman mean update
                S_cho_factors, lower = la.cho_factor(Sa.T) # Optional, used in places for S^-1, see scipy.linalg.cho_factor and scipy.linalg.cho_solve
                W = la.cho_solve((S_cho_factors , lower), (Ha @ P.T) ).T
                etaupd = eta + W @ v

                # Kalman cov update: use Joseph form for stability
                jo = -W @ Ha

                # same as adding Identity mat
                jo[np.diag_indices(jo.shape[0])] += 1
                Pupd = jo @ P @ jo.T + W @ np.kron(np.eye(za.size // 2), self.R) @ W.T 

                # calculate NIS, can use S_cho_factors
                NIS = la.cho_solve((S_cho_factors, lower), v) @ v    

                # When tested, remove for speed
                # assert np.allclose(
                #    Pupd, Pupd.T), "EKFSLAM.update: Pupd not symmetric"
                #assert np.all(
                #    np.linalg.eigvals(Pupd) > 0
                #), "EKFSLAM.update: Pupd not positive definite"

        else:  # All measurements are new landmarks,
            a = np.full(z.shape[0], -1)
            z = z.flatten()
            NIS = 1  # TODO: beware this one when analysing consistency.
            etaupd = eta
            Pupd = P

        # Create new landmarks if any is available
        if self.do_asso:
            is_new_lmk = a == -1
            if np.any(is_new_lmk):
                z_new_inds = np.empty_like(z, dtype=bool)
                z_new_inds[::2] = is_new_lmk
                z_new_inds[1::2] = is_new_lmk
                z_new = z[z_new_inds]
                etaupd, Pupd = self.add_landmarks(etaupd, Pupd, z_new)  

        # assert np.allclose(
        #     Pupd, Pupd.T), "EKFSLAM.update: Pupd must be symmetric"
        # assert np.all(np.linalg.eigvals(Pupd) >=
        #               0), "EKFSLAM.update: Pupd must be PSD"

        return etaupd, Pupd, NIS, a

    @classmethod
    def NEESes(cls, x: np.ndarray, P: np.ndarray, x_gt: np.ndarray,) -> np.ndarray:
        """Calculates the total NEES and the NEES for the substates
        Args:
            x (np.ndarray): The estimate
            P (np.ndarray): The state covariance
            x_gt (np.ndarray): The ground truth
        Raises:
            AssertionError: If any input is of the wrong shape, and if debug mode is on, certain numeric properties
        Returns:
            np.ndarray: NEES for [all, position, heading], shape (3,)
        """

        assert x.shape == (3,), f"EKFSLAM.NEES: x shape incorrect {x.shape}"
        assert P.shape == (3, 3), f"EKFSLAM.NEES: P shape incorrect {P.shape}"
        assert x_gt.shape == (
            3,), f"EKFSLAM.NEES: x_gt shape incorrect {x_gt.shape}"

        d_x = x - x_gt
        d_x[2] = utils.wrapToPi(d_x[2])
        assert (
            -np.pi <= d_x[2] <= np.pi
        ), "EKFSLAM.NEES: error heading must be between (-pi, pi)"

        d_p = d_x[0:2]
        P_p = P[0:2, 0:2]
        assert d_p.shape == (2,), "EKFSLAM.NEES: d_p must be 2 long"
        d_heading = d_x[2]  # Note: scalar
        assert np.ndim(
            d_heading) == 0, "EKFSLAM.NEES: d_heading must be scalar"
        P_heading = P[2, 2]  # Note: scalar
        assert np.ndim(
            P_heading) == 0, "EKFSLAM.NEES: P_heading must be scalar"

        # NB: Needs to handle both vectors and scalars! Additionally, must handle division by zero
        if np.linalg.det(P) != 0:
            NEES_all = d_x @ (np.linalg.solve(P, d_x))
            NEES_pos = d_p @ (np.linalg.solve(P_p, d_p))
        else:
            NEES_all = 1.0
            NEES_pos = 1.0

        try:
            NEES_heading = d_heading ** 2 / P_heading
        except ZeroDivisionError:
            NEES_heading = 1.0  # TODO: beware

        NEESes = np.array([NEES_all, NEES_pos, NEES_heading])
        NEESes[np.isnan(NEESes)] = 1.0  # We may divide by zero, # TODO: beware

        assert np.all(NEESes >= 0), "ESKF.NEES: one or more negative NEESes"
        return NEESes
