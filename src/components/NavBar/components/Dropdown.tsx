import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

const Dropdown = ({ setUserData, dropDownRef, profileRef }: any) => {
    const navigate = useNavigate();
    return <motion.div
        key="userMenu"
        ref={dropDownRef}
        className="userMenu"
        animate={{ maxHeight: "16vh" }}
        transition={{
            duration: 0.1,
            type: "spring",
            stiffness: 100,
            damping: 15,
        }}
        style={{ width: profileRef.current?.offsetWidth }}
        initial={{ maxHeight: "0vh" }}
        exit={{ maxHeight: "0vh" }}
    >
        <ul className="userMenuList">
            <li className="userMenuListItem"
                onClick={() => {
                    alert("Not implemented yet");
                }}
            >Dashboard</li>
            <li className="userMenuListItem"
                onClick={() => {
                    navigate("/sessions")
                }}
            >Account Sessions</li>
            <hr />
            <li
                onClick={() => {
                    fetch("http://localhost:8000/user/logout", {
                        method: "POST",
                        headers: {
                            "Authorization": "Token " + localStorage.getItem("session"),
                        }
                    })
                        .then(res => res.json())
                        .then(data => {
                            if (data.success) {
                                localStorage.removeItem("session");
                                setUserData({});
                            } else {
                                alert("Error logging out");
                            }
                        })
                }}

                className="userMenuListItem"
                id="sign out"
            >
                Sign Out
            </li>
        </ul>
    </motion.div>;
};

export default Dropdown;
