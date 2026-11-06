import { createContext, useContext } from "react";
import type { TeamDetail } from "../api/client";

export type Role = "coordinator" | "lead" | "specialist";

/** Agent key -> role in the current team, so blocks can colour their badges. */
export const RolesContext = createContext<Record<string, Role>>({});

export const useRole = (agent: string | null | undefined): Role | undefined =>
  useContext(RolesContext)[agent ?? ""];

export function rolesOf(team: TeamDetail | null): Record<string, Role> {
  if (!team) return {};
  const roles: Record<string, Role> = { [team.coordinator]: "coordinator" };
  for (const a of team.member_agents) roles[a.key] = "lead";
  for (const key of Object.keys(team.sub_agents)) roles[key] = "specialist";
  return roles;
}

export const TONE: Record<Role, "tomato" | "teal" | "mustard"> = {
  coordinator: "tomato",
  lead: "teal",
  specialist: "mustard",
};
