from .roots.athena_analysis import *

logging.basicConfig(filename=file.logs_loc+"/angular_momentum.log", encoding='utf-8', level=logging.INFO)

class AngularMomentum():
    def __init__(self, dname):
        self.dname = dname
        self.aname = "_angular_momentum" #a for analysis
        self.data_location = file.data_loc + dname
        self.grid_type = file.grid_types[dname]
        self.is_MHD = file.MHD[dname]
        self.alpha = file.alpha[dname]
        self.savedir = file.savedir + dname + "/" + dname + self.aname
        mkdir_if_not_exist(self.savedir)

        #finding file spacing
        max_fnum = 1
        self.file_spacing = None
        while self.file_spacing is None:
            while not os.path.exists("%s/disk.out1.%05d.athdf" % (self.data_location, max_fnum)):
                max_fnum += 1
            self.file_spacing = max_fnum

        self.time = None

    def angular_momentum_profile(self, fnum, plot=True):
        self.torques = {}
        if self.is_MHD:
            self.torque_list = ["tidal", "press", "flow", "Bpress", "Btens"]
        else:
            self.torque_list = ["tidal", "press", "flow", "alpha"]
        
        filename = "%s/disk.out1.%05d.athdf" % (self.data_location, fnum)
        aa = Athena_Analysis(filename=filename, grid_type=self.grid_type)
        if self.time is not None:
            self.previous_time = self.time
        self.time = aa.time

        aa.get_primaries(get_rho=True, get_press=True, get_vel_phi=True)
        aa.get_potentials(get_companion_grav=True, get_accel=True)

        #angular momentum
        self.L_z = aa.r*aa.rho*aa.vel_phi

        #computing torque densities for z direction, ie for each force density (r x f)_z = r*f_phi. Recall vectors in [z, phi, r] order
        self.torques["tidal"] = aa.r * (-1 * aa.rho * aa.gradient(aa.accel_pot + aa.companion_grav_pot, coordinates=self.grid_type))[1]
        self.torques["press"] = aa.r * (-1 * aa.gradient(aa.press, coordinates=self.grid_type))[1]
        self.torques["flow"] = -1 *aa.radial_transport(self.L_z)
        if self.is_MHD:
            self.torques["Bpress"] = aa.r * (-1 * aa.gradient(((aa.B_r ** 2) + (aa.B_theta ** 2) + (aa.B_phi ** 2)) / 2, coordinates=self.grid_type))[1]
            self.torques["Btens"] = aa.r * (aa.material_derivative([aa.B_phi, aa.B_theta, aa.B_r], [aa.B_phi, aa.B_theta, aa.B_r]))[1]
        else:
            self.torques["alpha"] = aa.alpha_torque(self.alpha)

        #Shell ave
        normalization_weight = aa.integrate(1, "shell")
        for key in self.torque_list:
            self.torques[key] = aa.integrate(self.torques[key], "shell") / normalization_weight
        self.L_z = aa.integrate(self.L_z, "shell") / normalization_weight

        self.r_axis = aa.possible_r

        if plot:
            #plot
            vert_num = 2
            horz_num = 1
            gs = gridspec.GridSpec(vert_num, horz_num)
            fig = plt.figure(figsize=(horz_num*3, vert_num*3), dpi=300)
            
            ax_L_z = fig.add_subplot(gs[0, 0])
            ax_torques = fig.add_subplot(gs[1, 0])

            ax_L_z.plot(aa.possible_r, self.L_z)
            for k, key in enumerate(self.torque_list):
                ax_torques.plot(aa.possible_r, self.torques[key], f"C{k}-", label=key)

            plt.legend()
            plt.savefig("%s/%s%s%05dtest.png" % (self.savedir, self.dname, self.aname, fnum))
            plt.close()

    def angular_momentum_history(self, fnum_range, step=None):
        if step is None:
            step = self.file_spacing
        fnum_range = np.arange(fnum_range[0], fnum_range[-1]+1, step)
        now = datetime.now()
        for i, fnum in enumerate(fnum_range):
            logging.info(f"fnum = {fnum}")
            logging.info(datetime.now()-now)
            now = datetime.now()
            self.angular_momentum_profile(fnum, plot=False)
            if i == 0 or i == 1:
                self.int_L_z = np.copy(self.L_z)
                dL_zdt = np.zeros(self.L_z.shape)
                for key in self.torque_list:
                    dL_zdt += self.torques[key]
            else:
                #self. quantities refer to previous timestep
                dL_zdt = np.zeros(self.L_z.shape)
                for key in self.torque_list:
                    dL_zdt += self.torques[key]
                self.int_L_z += (self.time - self.previous_time) * (dL_zdt + self.dL_zdt)/2

            #save values for use in next timestep
            self.dL_zdt = dL_zdt

            #plot
            vert_num = 2
            horz_num = 1
            gs = gridspec.GridSpec(vert_num, horz_num)
            fig = plt.figure(figsize=(horz_num*3, vert_num*3), dpi=300)
            
            ax_L_z = fig.add_subplot(gs[0, 0])
            ax_torques = fig.add_subplot(gs[1, 0])

            ax_L_z.plot(self.r_axis, self.L_z, "C2-", label="measured")
            ax_L_z.plot(self.r_axis, self.int_L_z, "C9--", label="integrated")
            ax_L_z.set_ylabel(r"$L_z$")
            for k, key in enumerate(self.torque_list):
                ax_torques.plot(self.r_axis, self.torques[key], f"C{k}-", label=key)
            ax_torques.set_ylabel(r"$\tau$")
            ax_torques.set_xlabel("r")

            orbit = (self.time / sim.binary_period)
            plt.subplots_adjust(top=(1-0.01*(16/vert_num)))
            fig.suptitle(f"orbit: {orbit:.2f}")
            plt.legend()
            plt.savefig("%s/%s%s%05d.png" % (self.savedir, self.dname, self.aname, fnum))
            plt.close()